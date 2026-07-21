# Developer Guide — v1.1.5 Stable

Guide for engineers working on the EU AI Regulation Monitor codebase.

---

## Prerequisites

- Python 3.11+
- Git
- API keys: OpenAI, Firecrawl
- Optional: Docker & Docker Compose

---

## Quick start

```bash
git clone <repository-url>
cd AI_Regulation_Project

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux/macOS

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

Start the dashboard:

```bash
uvicorn app.web.app:app --reload --host 0.0.0.0 --port 8080
```

Open http://localhost:8080

---

## Project structure

```
app/
  ai/                 OpenAI analysis and extraction
  core/               Logging, paths, JSON utilities
  crawler/            Firecrawl integration
  dev/                Local change-test site (development only)
  knowledge/          Knowledge builder, search, statistics
  monitors/
    repository.py     SQLiteMonitorRepository
    run_store.py      MonitorRunStore (run history)
    execution.py      Manual run orchestration
    categories.py     Category normalization and suggestions
    display_helpers.py UI label formatting
  pipeline.py         Monitoring pipeline
  report/             Weekly report generation
  scheduler.py        APScheduler jobs
  source/             Monitor loading and validation
  storage/            SQLite persistence (snapshots, diffs, knowledge)
  web/
    app.py            Dashboard application factory
    monitor_api.py    Monitor REST API
    run_api.py        Run Details API
    templates/        Jinja2 HTML templates
config/
  monitors.json       Seed monitors (not runtime source of truth)
  notification.json   Legacy notification config
  report.json         Report schedule config
data/
  storage.db          SQLite database
  raw/                Snapshot markdown files
  run_history.json    Batch run summaries
  reports/            Generated reports
tests/                Pytest suite (470 tests)
docs/                 Documentation
main.py               CLI entry point
VERSION               Release version (1.1.5)
```

---

## Key development concepts

### Monitor repository

`SQLiteMonitorRepository` in `data/storage.db` is the **canonical** monitor store. The UI, CLI, and scheduler all load monitors through `load_monitors()` → repository.

Seed behavior: new IDs from `config/monitors.json` are inserted once; existing IDs are never overwritten.

### Manual runs

```python
from app.monitors.execution import MonitorExecutionService

service = MonitorExecutionService()
result = service.run_monitor("monitor_id", triggered_by="manual_ui")
# result["run_history_id"] -> monitor_runs.id
```

### Categories

```python
from app.monitors.categories import normalize_category
from app.monitors.display_helpers import format_category_label

normalize_category("National Regulation")  # -> "national_regulation"
format_category_label("national_regulation")  # -> "National Regulation"
```

### Development test site

Set `APP_ENV=development` to enable the local multi-page change test site:

- `/dev/change-test-site`
- `/dev/change-test-site/controls`

See [MULTIPAGE_CHANGE_TEST.md](MULTIPAGE_CHANGE_TEST.md).

---

## Running tests

Full suite:

```bash
python -m pytest
```

Specific modules:

```bash
python -m pytest tests/test_monitor_categories.py -v
python -m pytest tests/test_monitor_run_regression.py -v
python -m pytest tests/test_monitor_ui_v115.py -v
```

With coverage (if pytest-cov installed):

```bash
python -m pytest --cov=app --cov-report=term-missing
```

**Release baseline:** 470 passing tests.

---

## CLI commands

```bash
python main.py run-once          # Run all enabled monitors once
python main.py scheduler         # Start APScheduler (blocking)
python main.py status            # Print monitor and run history status
python main.py generate-report   # Generate weekly report manually
python main.py demo              # Load demo summary
```

---

## Adding a monitor programmatically

```bash
curl -X POST http://localhost:8080/api/monitors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Regulation Source",
    "url": "https://example.com/regulation",
    "keywords": ["regulation"],
    "category": "eu_regulation",
    "frequency": "daily",
    "crawl_mode": "single",
    "max_depth": 0,
    "max_pages": 1,
    "enabled": true
  }'
```

---

## Code conventions

- Match existing module patterns and naming.
- Normalize monitor categories in the API layer, not in templates.
- Use `logger.exception()` for operational failures in execution paths.
- Prefer SQLite repository methods over direct JSON file edits.
- Do not commit `.env`, `data/storage.db`, or `logs/`.

---

## Debugging tips

| Issue | Check |
|-------|-------|
| Enabled monitors: 0 in CLI | CWD vs `data/storage.db`; use `log_monitor_repository_state` logs |
| Manual run 500 | `logs/app.log`; verify `data/run_history.json` path is writable |
| Dropdown not working | Single Bootstrap bundle load in `base.html` |
| Category blank in edit | Stored value must appear in datalist; check `/api/monitors/categories` |

View logs:

```bash
tail -f logs/app.log
```

---

## Related documents

- [Architecture.md](Architecture.md)
- [API.md](API.md)
- [Database.md](Database.md)
- [configuration.md](configuration.md) — environment variables
- [user-guide.md](user-guide.md) — operator usage
