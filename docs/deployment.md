# Deployment Guide

This guide covers Docker-based deployment of the AI Regulation Monitoring Platform for internal use.

## Prerequisites

- Docker
- Docker Compose

## Environment Setup

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for regulation analysis |
| `FIRECRAWL_API_KEY` | Firecrawl API key for web crawling |
| `SMTP_PASSWORD` | SMTP password for notification and report emails |

Do not commit `.env` to version control.

Persistent directories:

| Path | Purpose |
|------|---------|
| `data/` | SQLite database, snapshots, reports, run history |
| `config/` | Monitor, notification, and report configuration |
| `logs/` | Application log output |

## Logging

Application logs are written to the `logs/` directory (mounted as a volume in Docker):

| File | Level | Contents |
|------|-------|----------|
| `logs/app.log` | INFO and above | General operational messages (pipeline runs, scheduler jobs, report generation) |
| `logs/error.log` | ERROR | Failures and exceptions |

View logs on the host:

```bash
tail -f logs/app.log
tail -f logs/error.log
```

Or via Docker Compose:

```bash
docker compose logs -f dashboard
docker compose logs -f scheduler
```

## Health Check

The dashboard exposes a health endpoint for operational monitoring:

```bash
curl http://localhost:8080/health
```

Example response:

```json
{
  "status": "ok",
  "timestamp": "2026-07-16T16:30:00",
  "database": "ok",
  "scheduler": "ok"
}
```

| Field | Description |
|-------|-------------|
| `status` | Overall health (`ok` or `error`) |
| `timestamp` | Time of the health check |
| `database` | SQLite connectivity (`ok` or `error`) |
| `scheduler` | Last known scheduler state from `data/scheduler_status.json` (`ok`, `error`, `running`, or `unknown`) |

The dashboard Docker service includes a health check that polls `/health` every 30 seconds. Check container health:

```bash
docker compose ps
```

Scheduler job status is written to `data/scheduler_status.json` when jobs start, succeed, or fail.

## Troubleshooting

**Dashboard unhealthy**

- Confirm the container is running: `docker compose ps`
- Check `curl http://localhost:8080/health` for `database` status
- Inspect `logs/error.log` for connection or startup errors

**Scheduler shows `unknown` in health check**

- The scheduler runs in a separate container; status appears after the first job runs
- Verify the scheduler container is up: `docker compose logs scheduler`
- Inspect `data/scheduler_status.json` for job history

**No log files**

- Ensure the `logs/` directory exists and is writable
- Confirm volume mounts in `docker-compose.yml` include `./logs:/app/logs`

**Database errors**

- Verify `data/storage.db` is accessible and not locked by another process
- Check disk space on the host volume mount

## Build

```bash
docker compose build
```

Or build the image directly:

```bash
docker build -t ai-regulation-monitor .
```

## Start

```bash
docker compose up
```

Run in the background:

```bash
docker compose up -d
```

Services:

| Service | Container | URL / Purpose |
|---------|-----------|---------------|
| `dashboard` | `ai-regulation-dashboard` | http://localhost:8080 |
| `scheduler` | `ai-regulation-scheduler` | APScheduler jobs (monitors + weekly reports) |

## Stop

```bash
docker compose down
```

## View Logs

All services:

```bash
docker compose logs -f
```

Single service:

```bash
docker compose logs -f dashboard
docker compose logs -f scheduler
```

## Manual CLI (outside Docker)

```bash
python main.py run-once
python main.py scheduler
python main.py status
python main.py generate-report
```
