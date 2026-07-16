# Demo Mode Guide

This guide explains how to run AI Regulation Monitor in demo mode for management presentations, training, and stable walkthroughs without live API calls or production pipeline runs.

## Overview

Demo mode loads sample regulation data from `data/demo/` and presents a representative end-to-end flow:

1. Monitoring result (change detected)
2. AI impact analysis
3. Knowledge base item
4. Weekly report summary

Demo data is **examples only** — it is not written to the production database and does not invoke the crawler, AI analyzer, or pipeline.

## Enable Demo Mode

Edit `config/demo.json`:

```json
{
  "enabled": true
}
```

| Setting | Description |
|---------|-------------|
| `enabled: false` | Default — production behaviour unchanged |
| `enabled: true` | Marks the environment as demo-ready (shown in CLI output) |

The CLI `demo` command works regardless of this flag. Set `enabled: true` before presentations to document that the environment is configured for demos.

## Run Demo Mode

```bash
python main.py demo
```

No OpenAI or Firecrawl API keys are required for the demo command.

### Expected Output Sections

| Section | Description |
|---------|-------------|
| Demo configuration | Shows whether demo mode is enabled in `config/demo.json` |
| Monitoring result | Sample EU AI Act change detection result |
| AI impact analysis | MEDIUM impact with affected Smart TV modules |
| Knowledge item | Structured regulation record derived from demo data |
| Report summary | Weekly report totals and executive summary excerpt |

## Demo Data Files

Located in `data/demo/`:

| File | Contents |
|------|----------|
| `demo_snapshot.json` | Sample regulation page snapshot |
| `demo_analysis.json` | Sample AI impact analysis |
| `demo_report.json` | Sample weekly compliance report |

These files are safe to share internally and modify for presentation scenarios.

## Demo Flow (15 minutes)

Recommended live presentation sequence:

1. **CLI demo** — `python main.py demo` to show sample data without APIs
2. **Dashboard** — Start the web UI: `uvicorn app.web.app:app --host 0.0.0.0 --port 8080`
3. **Add source** — Manage Monitors → add EU AI Act URL (or show existing monitors)
4. **Run monitoring** — Optional: `python main.py run-once` if API keys are configured; otherwise skip and use demo output
5. **Review change** — Changes page → open a detected change
6. **Knowledge search** — Knowledge Base → search "AI Act"
7. **Insights** — Compliance Insights page
8. **Report** — Reports page → generate or show latest report

## Expected Screenshots

Capture these pages for Slide 8 of the management presentation (`docs/AI_Regulation_Monitor_v1.0_Presentation.pptx`):

| Screen | URL | What to show |
|--------|-----|--------------|
| Dashboard | `/` | Monitor count, last run, risk summary |
| Knowledge Base | `/knowledge` | Search results and regulation list |
| Compliance Insights | `/insights` | Impact and module groupings |
| Weekly Reports | `/reports` | Executive summary and key changes |

### CLI screenshot (optional)

Terminal output from `python main.py demo` showing all five sections.

## Docker Demo

For a containerized demo environment:

```bash
cp .env.example .env
# Set enabled: true in config/demo.json
docker compose up -d dashboard
python main.py demo
```

Open http://localhost:8080 for the dashboard.

## Troubleshooting

**Demo file not found**

Ensure `data/demo/` contains all three JSON files. They ship with the repository.

**Demo vs production**

Demo mode never modifies `data/storage.db`. Production runs use `run-once`, `scheduler`, and `generate-report`.

**API keys not required for demo CLI**

Only live monitoring and report generation require `OPENAI_API_KEY` and `FIRECRAWL_API_KEY`.

## Related Documents

- [User Guide](user-guide.md)
- [Presentation Content](presentation_content_v1.0.md)
- [Deployment Guide](deployment.md)
