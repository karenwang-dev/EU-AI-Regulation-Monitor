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
