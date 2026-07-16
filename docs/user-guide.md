# User Guide

This guide covers day-to-day use of the AI Regulation Monitoring Platform for internal compliance and engineering teams.

## Getting Started

1. Configure environment variables (see `docs/configuration.md`).
2. Start the dashboard: `uvicorn app.web.app:app --host 0.0.0.0 --port 8080`
3. Open http://localhost:8080

For automated monitoring, also run the scheduler: `python main.py scheduler`

## Add a Monitor Source

Monitors define which regulation websites to track.

### Via the Dashboard

1. Go to **Manage Monitors** (`/manage-monitors`).
2. Click **Add Monitor** and fill in:
   - **Name** — display name (e.g. "EU AI Act")
   - **URL** — official source page
   - **Keywords** — terms used for relevance filtering
   - **Category** — grouping label (e.g. "AI Regulation")
   - **Frequency** — `daily` or `weekly`
   - **Enabled** — toggle to include in scheduled runs
3. Save the monitor. Changes are written to `config/monitors.json`.

### Via Configuration File

Edit `config/monitors.json` directly and restart the scheduler if it is running.

Example monitor entry:

```json
{
  "id": "eu_ai_act",
  "name": "EU AI Act",
  "url": "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai",
  "keywords": ["AI Act", "smart TV"],
  "category": "AI Regulation",
  "frequency": "daily",
  "enabled": true
}
```

## Run Monitoring

### One-Time Run (All Enabled Monitors)

```bash
python main.py run-once
```

This crawls all enabled sources, compares snapshots, runs AI analysis on changes, and saves results.

### Scheduled Runs

```bash
python main.py scheduler
```

The scheduler runs:

- **Daily monitors** — every day at 08:00
- **Weekly monitors** — every Monday at 08:00
- **Weekly report** — every Monday at 08:30 (configurable in `config/report.json`)

### Check Status

```bash
python main.py status
```

Shows configured monitors and the most recent pipeline run summary.

## Review Regulation Changes

1. Open **Changes** (`/changes`) from the navigation bar.
2. Browse detected diffs sorted by date.
3. Filter by impact level (HIGH, MEDIUM, LOW) or search by keyword.
4. Click a change to open the **Detail** page with:
   - Diff content (added/removed text)
   - AI impact analysis
   - Affected product modules
   - Recommended actions
   - Source URL and discovery tree

The **Dashboard** home page shows today's change count and risk breakdown.

## Search the Knowledge Base

The knowledge base stores structured regulation items extracted from analyses.

1. Go to **Knowledge Base** (`/knowledge`).
2. Search by title, keyword, category, or module filter.
3. Open an item to view:
   - Full regulation metadata
   - Related regulations
   - Similar items
   - Regulation timeline
4. Visit **Knowledge Statistics** (`/knowledge/statistics`) for aggregate counts by category and module.

**Insights** (`/insights`) provides a compliance-focused view grouped by impact and affected modules.

## Generate Reports

### Manual Generation

```bash
python main.py generate-report
```

Or from the dashboard:

1. Go to **Reports** (`/reports`).
2. Click **Generate Report** to create a weekly report for the current period.
3. Review the executive summary, key changes, and risk overview.

Reports are saved as JSON in `data/reports/`.

### Scheduled Reports

When the scheduler is running, weekly reports are generated automatically per `config/report.json`. Email delivery is optional and requires `SMTP_PASSWORD` and recipient configuration.

### Demo Data

Sample files in `data/demo/` illustrate snapshot, analysis, and report JSON formats for training and demos. These files are not loaded by the application.

## Tips

- Use **Monitors** (`/monitors`) to see all configured sources and their settings.
- Check **About** (`/about`) for version info and configuration status.
- Use `GET /health` or `docker compose ps` to verify system health in deployed environments.
- Review `logs/app.log` for pipeline and scheduler activity.

## Further Reading

- [Architecture](architecture.md)
- [Configuration](configuration.md)
- [Deployment](deployment.md)
