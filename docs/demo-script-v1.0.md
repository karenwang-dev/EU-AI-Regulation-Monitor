# AI Regulation Monitor v1.0.0 — Demo Presentation Script

**Duration:** 15 minutes (+ optional 5 minutes Q&A)  
**Audience:** Engineering managers, product managers, compliance team  
**Presenter:** Platform owner / compliance lead  
**Environment:** Dashboard at http://localhost:8080 (Docker or local Uvicorn)

---

## Pre-Demo Checklist

- [ ] Dashboard running: `uvicorn app.web.app:app --host 0.0.0.0 --port 8080` or `docker compose up -d dashboard`
- [ ] Optional: set `config/demo.json` → `"enabled": true`
- [ ] Optional backup: run `python main.py demo` in a terminal if live data is sparse
- [ ] Browser tab pre-loaded: `/` (Dashboard home)
- [ ] Confirm at least one change exists in the Changes page; otherwise use demo CLI output as narrative backup
- [ ] Close unrelated browser tabs; zoom to 100–110% for projector readability

---

## Section 1 — Introduction (1 minute)

### Screen / Page
- **Primary:** Dashboard home — `/`
- **Optional:** Terminal with `python main.py demo` output visible in split view for first 30 seconds, then switch to browser

### Key Message
> AI Regulation Monitor v1.0.0 gives our Smart TV and connected device teams a single internal platform to detect EU regulation changes, understand product impact, and report compliance status — without manual website checking.

### Speaker Notes

Good morning. Today I will walk you through **AI Regulation Monitor**, our internal v1.0 release for Smart TV product compliance.

The problem we are solving is straightforward: regulation updates are scattered across dozens of official websites. Engineers and compliance staff spend time manually checking pages, and it is difficult to quickly answer — *does this change affect our product, and what should we do?*

This platform automates monitoring, applies AI to interpret changes, stores structured knowledge, and produces weekly compliance reports. It is deployed internally via Docker, requires no external authentication, and is production-ready with **261 automated tests**.

I will show you the full workflow in about fifteen minutes. Please hold questions until the end, though I have anticipated several throughout the script.

### Expected Questions

| Question | Suggested Response |
|----------|-------------------|
| Is this a commercial product? | No — it is an internal tool for our compliance and engineering teams. |
| Does it replace legal review? | No — it accelerates detection and triage; compliance and legal still sign off on actions. |
| What regulation scope is covered today? | Primarily EU sources relevant to Smart TV, DVB, HbbTV, AI Act, and product compliance. |

---

## Section 2 — Dashboard Overview (2 minutes)

### Screen / Page
- **URL:** `/` (Dashboard home)
- **Navigation highlight:** Dashboard (active in top nav)

### Key Message
> The dashboard is the operational command centre — one view of monitor coverage, recent activity, and compliance risk distribution.

### Speaker Notes

This is the **Dashboard home page**, our starting point for daily compliance awareness.

At the top you see summary metrics:

- **Configured monitors** — how many regulation sources we track
- **Last run** — when the pipeline last executed (scheduled or manual)
- **Today's changes** — diffs detected in the current period
- **Risk breakdown** — HIGH, MEDIUM, and LOW impact counts from AI analysis

These numbers come from our SQLite database and run history — they update automatically after each scheduled or manual monitoring run.

The navigation bar gives access to every major capability: **Monitors**, **Changes**, **Knowledge Base**, **Insights**, **Reports**, and **Manage Monitors** for configuration.

For operations, we also expose a **health endpoint** at `/health` and an **About** page at `/about` showing version 1.0.0 and configuration status. In Docker deployments, the dashboard container health check polls this endpoint every thirty seconds.

If you are responsible for a product line, this page answers the first question each morning: *has anything changed, and how serious is it?*

### Expected Questions

| Question | Suggested Response |
|----------|-------------------|
| How often does data refresh? | Daily monitors run at 08:00; weekly monitors on Monday 08:00; reports Monday 08:30. Manual runs available anytime. |
| Can we add new sources without code changes? | Yes — via Manage Monitors or `config/monitors.json`. |
| What if the dashboard shows zero changes? | Either no source changed, or use `python main.py demo` to illustrate the workflow with sample EU AI Act data. |

---

## Section 3 — Regulation Change Detection (3 minutes)

### Screen / Page
- **URL:** `/changes` (Changes list)
- **Then:** `/detail/{diff_id}` (Change detail — open any HIGH or MEDIUM item, ideally EU AI Act)

### Key Message
> The platform detects content changes automatically through snapshot comparison — engineers no longer need to manually diff regulation web pages.

### Speaker Notes

Let me move to the **Changes** page.

Every row represents a detected difference between a previous snapshot and the current version of a regulation source. The pipeline works as follows:

1. **Smart Crawler** fetches the configured URL (and linked pages within depth limits)
2. A new **snapshot** is stored on disk and in the database
3. **Change Detection** compares the new snapshot to the previous one
4. If content changed, the item appears here with date, source, impact level, and summary

You can **filter by impact** — HIGH, MEDIUM, LOW — or **search by keyword**, source name, or affected module. Pagination supports large change histories.

Let me open a specific change — I will use an **EU AI Act** example.

On the **Change Detail** page you see:

- The **diff** — added and removed text highlighted
- The **source URL** and discovery context
- A **source tree** showing how the page was found during crawling
- Links to the related **analysis** and knowledge record

This is the critical handoff point: the system tells us *something changed* before anyone opens the original website. First snapshots establish a baseline; only subsequent changes trigger analysis.

If live data is unavailable during this demo, the CLI command `python main.py demo` shows an equivalent EU AI Act monitoring result with status `analyzed` and a sample diff narrative.

### Expected Questions

| Question | Suggested Response |
|----------|-------------------|
| How do we avoid false positives from layout changes? | Content hashing and diff logic focus on meaningful text changes; crawl cache reduces redundant fetches. |
| Does it support PDF regulations? | Yes — PDF sources can be ingested alongside HTML pages. |
| Can we trace where a page was found? | Yes — the source tree on the detail page shows discovery path and depth. |

---

## Section 4 — AI Impact Analysis (3 minutes)

### Screen / Page
- **URL:** `/detail/{diff_id}` (same Change detail page — scroll to AI analysis section)
- **Backup reference:** Terminal output from `python main.py demo` → "AI Impact Analysis" section

### Key Message
> AI analysis translates regulation language into Smart TV product impact — risk level, affected modules, and recommended engineering actions.

### Speaker Notes

Now the core value of the platform: **AI Impact Analysis**.

When a meaningful change is detected, our OpenAI integration evaluates the diff in the context of Smart TV product modules — for example:

- Browser / HbbTV  
- Voice assistant  
- AI features  
- Cybersecurity controls  
- OTA update  
- Network services  
- Remote control / voice input  

For each change, the analysis returns:

| Field | Purpose |
|-------|---------|
| **Impact level** | HIGH, MEDIUM, or LOW — for prioritization |
| **Affected modules** | Which product areas may need review |
| **Reason** | Plain-language explanation of why this matters |
| **Recommended actions** | Specific next steps for engineering or compliance |
| **Confidence** | Model confidence in the assessment |

In our demo scenario — an **EU AI Act update** — you would typically see **MEDIUM** impact affecting **AI features**, **Voice assistant**, and **Cybersecurity controls**, with actions such as reviewing AI risk classification and updating technical documentation.

This replaces the manual step where an engineer reads a fifty-page policy update and tries to infer Smart TV relevance. The AI does first-pass triage; your team validates and acts.

Important: **human review remains in the loop**. The platform accelerates awareness — it does not replace compliance sign-off.

Our demo data in `data/demo/demo_analysis.json` mirrors this structure for stable presentations without live API calls.

### Expected Questions

| Question | Suggested Response |
|----------|-------------------|
| Which AI model is used? | OpenAI via our configured API; model settings in `app/core/config.py`. |
| Can we trust the impact level? | Treat it as a triage signal — compliance validates before action. |
| What if the AI returns invalid output? | The pipeline logs the error and stores what it can; invalid JSON is handled gracefully without blocking the run. |

---

## Section 5 — Knowledge Base (2 minutes)

### Screen / Page
- **URL:** `/knowledge` (Knowledge Base list)
- **Search:** enter `AI Act` or `eu_ai_act`
- **Optional drill-down:** `/knowledge/{item_id}` (Knowledge detail)

### Key Message
> Every analyzed regulation becomes a searchable, reusable knowledge asset — building institutional memory beyond individual engineers.

### Speaker Notes

Next, the **Knowledge Base** at `/knowledge`.

When the pipeline analyzes a change, it also builds a **structured knowledge item** — title, category, modules, summary, and metadata extracted from the regulation content.

From this page you can:

- **Search** by keyword across all accumulated items  
- **Filter** by category (e.g. AI Regulation, Product Compliance) or product module  
- **Open any item** for full detail  

On the **Knowledge Detail** page you will find:

- Full regulation metadata and creation timestamp  
- **Related regulations** — amendments, guidance, supersession links  
- **Similar items** — semantic similarity to other knowledge records  
- **Regulation timeline** — chronological view of related updates  

This is how we convert one-off email alerts into a **durable compliance library**. When team members change roles, the knowledge stays.

For the demo, search **"AI Act"** to locate the EU AI Act item. The CLI demo also prints a sample knowledge item with title, category, modules, and summary.

Optionally visit `/knowledge/statistics` after the demo for aggregate counts by category and module — useful for quarterly compliance reviews.

### Expected Questions

| Question | Suggested Response |
|----------|-------------------|
| Is knowledge automatically created for every change? | Yes, when analysis completes successfully during a pipeline run. |
| Can we export knowledge items? | Today they are stored in SQLite; export can be added in v2.0 (vector search / RAG planned). |
| How are related regulations determined? | Heuristic relationship builder links amendments, guidance, and supersession based on titles and metadata. |

---

## Section 6 — Compliance Insights (2 minutes)

### Screen / Page
- **URL:** `/insights` (Compliance Insights)

### Key Message
> Compliance Insights aggregates knowledge into an executive-friendly view — grouped by impact, category, and affected product module.

### Speaker Notes

The **Compliance Insights** page at `/insights` is designed for managers and compliance leads who need the **big picture**, not individual diffs.

It aggregates all knowledge items into insight cards showing:

- Regulation title and summary  
- Impact level and category  
- Affected Smart TV modules  
- Source reference  

You can filter by **query**, **category**, **module**, and **impact** — the same filters engineering uses, but presented as a compliance dashboard.

The summary panel at the top shows counts by impact level for the current filter set — useful for stand-up meetings and status reports.

Where the Changes page answers *"what changed today?"*, Insights answers *"what is our overall compliance exposure across AI, cybersecurity, and product safety themes?"*

This is particularly valuable for product managers planning roadmap priorities — if three MEDIUM-impact items affect **OTA update** in the same month, that signals a cross-team review.

### Expected Questions

| Question | Suggested Response |
|----------|-------------------|
| How is this different from the Changes page? | Changes is event-driven (individual diffs); Insights is aggregated compliance intelligence across all knowledge. |
| Can we share this view with leadership? | Yes — it is web-based; capture screenshots or use the weekly report for formal distribution. |
| Does it update in real time? | It reflects the latest knowledge base after each pipeline run. |

---

## Section 7 — Weekly Report (2 minutes)

### Screen / Page
- **URL:** `/reports` (Weekly Reports)
- **Optional action:** click **Generate Report** if API keys are configured
- **Backup:** reference `data/demo/demo_report.json` or CLI demo "Report Summary" section

### Key Message
> Weekly AI reports give leadership a concise, period-based compliance summary — executive narrative, key changes, and risk overview with optional email delivery.

### Speaker Notes

I will close with **Weekly Reports** at `/reports`.

Each week — by default Monday at 08:30 — the scheduler can automatically:

1. Aggregate all changes in the reporting period  
2. Generate an **AI executive summary**  
3. List **key changes** with impact and recommended actions  
4. Save the report as JSON in `data/reports/`  
5. Optionally **email** the report to configured recipients  

On this page you see:

- **Report period** (start and end dates)  
- **Summary metrics** — total changes, HIGH/MEDIUM/LOW counts, affected modules  
- **Executive summary** — narrative suitable for management  
- **Key changes** — top items with actions  
- **Email status** — Sent, Disabled, or Failed  

You can also generate a report manually:

```bash
python main.py generate-report
```

Our demo report (`2026-07-16_weekly_report_demo`) shows two changes — one MEDIUM EU AI Act item and one LOW product compliance notice — with the executive summary: *no immediate blocking compliance actions required*.

This is the deliverable compliance can forward to engineering leadership each week without manual report writing.

### Expected Questions

| Question | Suggested Response |
|----------|-------------------|
| Who receives the email report? | Configured in `config/report.json` under `recipients`; requires SMTP setup. |
| Can we change the schedule? | Yes — day, hour, and minute in `config/report.json`. |
| Is the report suitable for audit evidence? | It supports awareness and tracking; formal audit packages may require additional legal review and sign-off. |

---

## Closing (30 seconds — within 15-minute block)

### Screen / Page
- **URL:** `/about` (About page) — optional
- **Or return to:** `/` (Dashboard home)

### Key Message
> AI Regulation Monitor v1.0.0 is release-ready — automated monitoring, AI-assisted triage, searchable knowledge, and weekly reporting for Smart TV compliance.

### Speaker Notes

To summarize: **AI Regulation Monitor v1.0.0** delivers a complete internal workflow — from automated change detection through AI impact analysis, knowledge accumulation, compliance insights, and weekly reporting.

It is **Docker-deployable**, **fully tested** with 261 automated tests, and available today for internal use. The v2.0 roadmap includes RAG chatbot, vector search, Jira integration, and Teams notifications.

Thank you. I am happy to take questions.

---

## Appendix A — Timing Guide

| Section | Duration | Cumulative |
|---------|----------|------------|
| 1. Introduction | 1:00 | 1:00 |
| 2. Dashboard overview | 2:00 | 3:00 |
| 3. Change detection | 3:00 | 6:00 |
| 4. AI impact analysis | 3:00 | 9:00 |
| 5. Knowledge Base | 2:00 | 11:00 |
| 6. Compliance Insights | 2:00 | 13:00 |
| 7. Weekly Report | 2:00 | 15:00 |

---

## Appendix B — Fallback Plan (No Live Data)

If the database has no recent changes or API keys are unavailable:

1. Run `python main.py demo` in a visible terminal (30 seconds)
2. Narrate sections 3–4 and 7 using CLI output
3. Show Knowledge and Insights pages explaining they populate after pipeline runs
4. Open `data/demo/demo_report.json` in an editor if the Reports page is empty

---

## Appendix C — Quick Reference URLs

| Page | URL |
|------|-----|
| Dashboard | http://localhost:8080/ |
| Monitors | http://localhost:8080/monitors |
| Changes | http://localhost:8080/changes |
| Knowledge Base | http://localhost:8080/knowledge |
| Compliance Insights | http://localhost:8080/insights |
| Weekly Reports | http://localhost:8080/reports |
| Manage Monitors | http://localhost:8080/manage-monitors |
| About | http://localhost:8080/about |
| Health check | http://localhost:8080/health |

---

## Appendix D — Related Documents

- [Demo Guide](demo-guide.md)
- [User Guide](user-guide.md)
- [Presentation Content](presentation_content_v1.0.md)
- [Release Notes v1.0](release_notes_v1.0.md)

---

*Script version: 1.0 — aligned with AI Regulation Monitor release v1.0.0*
