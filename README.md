# AI Regulation Monitoring Platform

An internal platform for monitoring EU and related regulation sources, detecting website changes, analyzing compliance impact with AI, and producing structured reports for Smart TV, DVB, CI+, HbbTV, and connected device teams.

## Features

- **Multi-source monitoring** — track official regulation websites with configurable daily/weekly schedules
- **Change detection** — snapshot comparison and diff generation for page content updates
- **AI impact analysis** — OpenAI-powered assessment of risk level, affected modules, and recommended actions
- **Knowledge base** — searchable regulation items with relationships, statistics, and timelines
- **Compliance insights** — dashboard views grouped by impact, category, and product module
- **Weekly reports** — AI-generated executive summaries with optional email delivery
- **Web dashboard** — FastAPI/Jinja2 UI for monitors, changes, knowledge, reports, and insights
- **Operational monitoring** — centralized logging, health checks, and configuration validation
- **Docker deployment** — containerized dashboard and scheduler services

## Architecture Summary

```
Monitor Sources → Crawler → Diff Engine → AI Analyzer → Knowledge Base
                              ↓                              ↓
                         SQLite Storage  ←  Dashboard (FastAPI)
                              ↓
                    Report Generator → Weekly Reports / Email
```

Scheduler (APScheduler) triggers pipeline runs and weekly report jobs. See [docs/architecture.md](docs/architecture.md) for the full system diagram.

## Tech Stack

- Python 3.11
- FastAPI + Uvicorn + Jinja2
- APScheduler
- Firecrawl (web crawling)
- OpenAI (analysis and reports)
- SQLite (persistence)

## Installation

### Prerequisites

- Python 3.11+
- API keys for OpenAI and Firecrawl

### Local Setup

```bash
git clone <repository-url>
cd AI_Regulation_Project

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your credentials. See [docs/configuration.md](docs/configuration.md) for details.

## Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | Regulation analysis and report generation |
| `FIRECRAWL_API_KEY` | Yes | Web crawling |
| `SMTP_PASSWORD` | No | Email notifications and report delivery |

Monitor sources: `config/monitors.json`  
Notifications: `config/notification.json`  
Reports: `config/report.json`

Demo sample files (examples only): `data/demo/`

## Running the Dashboard

```bash
uvicorn app.web.app:app --host 0.0.0.0 --port 8080
```

Open http://localhost:8080

Pages: Dashboard, Monitors, Changes, Knowledge Base, Insights, Reports, Manage Monitors, About

Health check: `GET http://localhost:8080/health`

## Running the Scheduler

```bash
python main.py scheduler
```

Runs daily monitors (08:00), weekly monitors (Monday 08:00), and weekly report generation (Monday 08:30, configurable).

### Other CLI Commands

```bash
python main.py run-once          # Run all enabled monitors once
python main.py status            # Show monitor and run history status
python main.py generate-report   # Generate a weekly report manually
```

## Report Generation

Reports aggregate regulation changes over a configurable period, generate an AI executive summary, and save JSON to `data/reports/`.

- **Manual:** `python main.py generate-report` or use the Reports page in the dashboard
- **Scheduled:** enabled via `config/report.json` when the scheduler is running
- **Email:** optional delivery when SMTP is configured

See [docs/user-guide.md](docs/user-guide.md) for step-by-step usage.

## Testing

```bash
python -m pytest
```

Run a specific test file:

```bash
python -m pytest tests/test_about_page.py -v
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | System design and Mermaid diagram |
| [docs/user-guide.md](docs/user-guide.md) | Day-to-day usage |
| [docs/configuration.md](docs/configuration.md) | Environment variables |
| [docs/deployment.md](docs/deployment.md) | Docker deployment |

## Docker Deployment

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Dashboard: http://localhost:8080  
See [docs/deployment.md](docs/deployment.md) for logging, health checks, and troubleshooting.

## Project Structure

```
app/
  ai/           AI analysis and extraction
  crawler/      Firecrawl integration
  knowledge/    Knowledge base builder and search
  pipeline.py   Monitoring pipeline orchestration
  report/       Weekly report generation
  scheduler.py  APScheduler jobs
  storage/      SQLite persistence
  web/          FastAPI dashboard
config/         Monitor, notification, and report settings
data/           Database, snapshots, reports, demo samples
docs/           Architecture, user guide, deployment
tests/          Unit and integration tests
```

## License

Internal use only.
