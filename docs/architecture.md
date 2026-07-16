# System Architecture

The AI Regulation Monitoring Platform is an internal tool that crawls official regulation sources, detects content changes, analyzes impact with AI, stores structured knowledge, and presents results through a web dashboard.

## Architecture Diagram

```mermaid
flowchart TB
    subgraph Client["Web Dashboard"]
        UI[Jinja2 Templates]
        Pages[Dashboard / Changes / Knowledge / Reports / Insights]
    end

    subgraph API["FastAPI"]
        Routes[REST & HTML Routes]
        Health[/health]
    end

    subgraph Jobs["Scheduler"]
        APScheduler[APScheduler]
        Daily[Daily Monitors]
        Weekly[Weekly Monitors]
        ReportJob[Weekly Report Job]
    end

    subgraph Pipeline["Monitoring Pipeline"]
        Crawler[Crawler]
        Diff[Diff Engine]
        AI[AI Analyzer]
        Knowledge[Knowledge Builder]
        Notify[Notifier]
    end

    subgraph Reports["Report Generator"]
        Builder[Report Data Builder]
        AIGen[AI Report Generator]
        Email[Email Delivery]
    end

    subgraph Storage["Storage"]
        SQLite[(SQLite DB)]
        RawFiles[Raw Snapshots]
        Reports[Report JSON]
        Status[Scheduler Status]
    end

    UI --> Routes
    Pages --> Routes
    Health --> SQLite

    APScheduler --> Daily
    APScheduler --> Weekly
    APScheduler --> ReportJob

    Daily --> Pipeline
    Weekly --> Pipeline
    ReportJob --> Reports

    Pipeline --> Crawler
    Crawler --> Diff
    Diff --> AI
    AI --> Knowledge
    Knowledge --> Notify

    Pipeline --> SQLite
    Pipeline --> RawFiles
    Knowledge --> SQLite

    Builder --> SQLite
    Builder --> AIGen
    AIGen --> Reports
    AIGen --> Email

    Routes --> SQLite
    Routes --> Reports
```

## Components

| Component | Location | Role |
|-----------|----------|------|
| Web Dashboard | `app/web/` | HTML UI for monitors, changes, knowledge, insights, and reports |
| FastAPI | `app/web/app.py` | HTTP server, page routes, REST APIs, health checks |
| Scheduler | `app/scheduler.py` | Runs daily/weekly monitor jobs and scheduled report generation |
| Crawler | `app/crawler/` | Fetches regulation pages via Firecrawl with caching and link discovery |
| AI Analyzer | `app/ai/` | OpenAI-powered impact analysis and regulation extraction |
| Knowledge Base | `app/knowledge/` | Builds searchable knowledge items, relationships, and statistics |
| Report Generator | `app/report/` | Weekly report data assembly, AI narrative, storage, and email |
| Storage | `app/storage/` | SQLite persistence for snapshots, diffs, analyses, and knowledge |

## Data Flow

1. **Monitor run** — Scheduler or CLI triggers the pipeline for enabled monitors.
2. **Crawl** — Firecrawl retrieves page content; snapshots are saved to disk and SQLite.
3. **Diff** — New content is compared to the previous snapshot.
4. **Analyze** — When content changes, OpenAI assesses impact level and affected product modules.
5. **Knowledge** — Structured regulation items are stored with relationships and metadata.
6. **Notify** — Optional email alerts are sent for significant changes.
7. **Report** — Weekly jobs aggregate changes into an AI-generated compliance report.
8. **Dashboard** — Teams review changes, search knowledge, and download reports via the web UI.

## External Dependencies

| Service | Purpose |
|---------|---------|
| Firecrawl | Web crawling and content extraction |
| OpenAI | Regulation change analysis and report narrative |
| SMTP | Email notifications and weekly report delivery |

## Configuration

- `config/monitors.json` — monitor sources, keywords, and schedules
- `config/notification.json` — SMTP settings
- `config/report.json` — weekly report schedule and email recipients
- `.env` — API keys and secrets (see `docs/configuration.md`)

## Deployment

The platform runs as two Docker services:

- **dashboard** — FastAPI on port 8080
- **scheduler** — background APScheduler process

See `docs/deployment.md` for build and run instructions.
