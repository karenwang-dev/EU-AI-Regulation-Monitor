# Configuration Guide

This document describes environment variables used by the AI Regulation Monitoring Platform.

## Environment File

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Docker Compose loads `.env` automatically. For local CLI usage, variables are read from the environment (including `.env` via `python-dotenv` in `app/core/config.py`).

## Environment Variables

### Required

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Authenticates OpenAI API calls for regulation analysis and report generation |
| `FIRECRAWL_API_KEY` | Authenticates Firecrawl API calls for web crawling |

Both keys must be set for pipeline runs, scheduled jobs, and AI-powered features.

### Optional

| Variable | Purpose |
|----------|---------|
| `SMTP_PASSWORD` | SMTP password for email notifications and weekly report delivery |

If `SMTP_PASSWORD` is not set, the platform still runs. Email delivery is skipped or fails gracefully when notifications are enabled without credentials.

## Validation

Configuration is validated at startup:

- **CLI** (`main.py`): before `run-once`, `scheduler`, `status`, or `generate-report`
- **Dashboard** (`app/web/app.py`): on application startup
- **Health API** (`GET /health`): reports current configuration status

Validation never raises exceptions. Results look like:

```json
{
  "status": "ok",
  "missing": [],
  "warnings": []
}
```

When required variables are missing:

```json
{
  "status": "warning",
  "missing": ["OPENAI_API_KEY"],
  "warnings": ["SMTP_PASSWORD is not set (optional)"]
}
```

## Health Check

The `/health` endpoint includes configuration status:

```json
{
  "status": "warning",
  "timestamp": "2026-07-16T17:30:00",
  "database": "ok",
  "scheduler": "unknown",
  "configuration": "warning",
  "missing_config": ["OPENAI_API_KEY"]
}
```

| Field | Description |
|-------|-------------|
| `configuration` | `ok` when all required variables are set, otherwise `warning` |
| `missing_config` | List of required environment variables that are missing or empty |

Overall `status` is `warning` when required configuration is missing, `error` when the database check fails, and `ok` otherwise.

## Security Notes

- Do not commit `.env` to version control
- Use separate keys for development and production where possible
- Rotate API keys if they are exposed
