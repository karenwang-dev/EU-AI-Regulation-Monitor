# Release Notes — v1.0.0

**Release date:** July 2026  
**Product:** AI Regulation Monitor  
**Version:** 1.0.0

## Overview

AI Regulation Monitor v1.0 is the first production-ready internal release of the AI Regulation Monitoring Platform. It provides end-to-end monitoring of EU and related regulation sources for Smart TV, DVB, CI+, HbbTV, and connected device compliance teams.

This release focuses on a complete monitoring pipeline, web dashboard, knowledge base, weekly reporting, Docker deployment, and operational tooling — without external authentication (internal use only).

## Main Features

### Monitoring & Analysis
- Multi-source monitor configuration (daily/weekly schedules)
- Firecrawl-based web crawling with caching and smart link discovery
- Snapshot storage and content diff detection
- OpenAI-powered impact analysis with risk levels and affected product modules
- Email notifications for significant changes (optional SMTP)

### Knowledge & Insights
- Structured knowledge base with search, categories, and module filters
- Regulation relationships (amendments, guidance, supersession)
- Similarity search and regulation timelines
- Compliance insights dashboard grouped by impact and module

### Reporting
- Weekly report data builder aggregating period changes
- AI-generated executive summaries and key change narratives
- Report storage, dashboard viewing, and optional email delivery
- Scheduled weekly report generation via APScheduler

### Web Dashboard
- Dashboard home with run statistics and risk counts
- Monitors, Changes, Knowledge Base, Insights, and Reports pages
- Monitor management UI with categories and scheduling
- Change detail view with diff, analysis, and source tree
- About page with version and configuration status

### Operations & Deployment
- Centralized logging (`logs/app.log`, `logs/error.log`)
- Health API (`GET /health`) with database, scheduler, and configuration checks
- Configuration validation at CLI and dashboard startup
- Docker Compose deployment (dashboard + scheduler services)
- Demo data package (`data/demo/`) for training and presentations

## Architecture

```
Monitor Sources → Crawler → Diff Engine → AI Analyzer → Knowledge Base
                              ↓                              ↓
                         SQLite Storage  ←  Dashboard (FastAPI)
                              ↓
                    Report Generator → Weekly Reports / Email
```

**Components:** Web Dashboard, FastAPI, Scheduler, Crawler, AI Analyzer, Knowledge Base, Report Generator, Storage (SQLite + JSON files).

See [architecture.md](architecture.md) for the full Mermaid diagram and data flow.

## Deployment

### Docker (recommended)

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

- Dashboard: http://localhost:8080
- Scheduler: background APScheduler container
- Volumes: `./data`, `./config`, `./logs`

### Local CLI

```bash
pip install -r requirements.txt
python main.py run-once
python main.py scheduler
uvicorn app.web.app:app --host 0.0.0.0 --port 8080
```

See [deployment.md](deployment.md) and [configuration.md](configuration.md) for full instructions.

## Known Limitations

- **No authentication** — intended for trusted internal networks only
- **Single-node SQLite** — not designed for high-concurrency multi-user writes
- **External API dependency** — requires OpenAI and Firecrawl availability and valid API keys
- **English-focused UI** — dashboard and reports are English-only
- **Email optional** — notifications and report delivery require SMTP configuration
- **Scheduler visibility** — dashboard health shows scheduler status via shared JSON file, not live process introspection
- **Crawl variability** — third-party site structure changes may affect discovery and extraction quality
- **No built-in backup** — operators must back up `data/` and `config/` volumes manually

## Upgrade Path

Future releases will increment the `VERSION` file. Check `docs/release_notes_*.md` for change history.

## Documentation Index

| Document | Description |
|----------|-------------|
| [README.md](../README.md) | Project overview and quick start |
| [architecture.md](architecture.md) | System design |
| [user-guide.md](user-guide.md) | Day-to-day usage |
| [configuration.md](configuration.md) | Environment variables |
| [deployment.md](deployment.md) | Docker and operations |
| [test_report.md](test_report.md) | v1.0 test results |
