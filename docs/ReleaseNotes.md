# Release Notes — v1.1.5 Stable

**Release date:** 2026-07-21  
**Version:** 1.1.5  
**Status:** Stable  
**Tests:** 470 passing

---

## Summary

v1.1.5 Stable completes the monitor operations and observability layer introduced across v1.1.3–v1.1.4. The platform now supports **multi-page change detection**, a **unified SQLite monitor repository**, **manual monitor runs from the UI**, **persistent run history with a Run Details page**, **polished Monitor Management UI**, and **extensible category management**.

This release is intended for internal Smart TV and connected-device compliance teams running the platform on trusted networks.

---

## Highlights

### Multi-page monitoring

Monitors can crawl a homepage plus discovered child pages (`crawl_mode: multi_page` or `smart`). Each page is snapshotted and compared independently. Run summaries report:

- Pages checked / changed
- Homepage vs child page changes
- Per-page status (changed, unchanged, baseline, failed)

### SQLite monitor repository

All monitor CRUD and enable/disable state lives in `data/storage.db`:

- `monitors` — full monitor configuration as JSON
- `monitor_execution` — last run metadata per monitor
- `monitor_runs` — historical run records with page-level JSON

`config/monitors.json` remains a **seed file** for first-time import only.

### Manual monitoring

From **Monitors** in the dashboard:

1. Click **Run** on any monitor row.
2. View result summary with links to Run Details and Changes.
3. Last Run, Last Status, and Pages Changed columns update from SQLite.

CLI and scheduler paths continue to work alongside manual runs.

### Run Details

- **API:** `GET /api/runs/{run_history_id}`
- **Page:** `/runs/{run_history_id}`

Shows execution status, change result, timing, page counts, and a page-results table. Legacy runs without page-level JSON display a clear fallback message.

### Monitor Management UI

- Primary **Run** action plus **More** dropdown (Edit, Enable/Disable, View Last Run, Delete).
- Responsive horizontal-scroll table with compact badges.
- Separate **execution status** (success/failed/running) from **change result** (changed/unchanged/baseline/failed).

### Category management

- Stored categories are machine-friendly (`national_regulation`).
- UI shows human-readable labels (National Regulation).
- Create/Edit uses text input + datalist with built-in and custom suggestions.
- Categories normalize on save; existing values are never silently cleared.

---

## Upgrade notes

1. Pull the v1.1.5 tag or branch.
2. No destructive database migration — new tables/columns are created automatically on startup.
3. Existing monitors in SQLite are preserved; seed file will not overwrite them.
4. Restart dashboard and scheduler containers after upgrade.

```bash
docker compose down
docker compose build
docker compose up -d
```

---

## Known limitations

- Scheduled/CLI batch runs write JSON run history; full `monitor_runs` persistence is guaranteed for manual UI runs.
- v1.2.0 features (Website Explorer, Page Tree, etc.) are planned but not included in this release.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture.md](Architecture.md) | System design |
| [API.md](API.md) | REST endpoints |
| [Database.md](Database.md) | SQLite schema |
| [DeveloperGuide.md](DeveloperGuide.md) | Local development |
| [Deployment.md](Deployment.md) | Docker deployment |
| [Roadmap.md](Roadmap.md) | v1.2.0 direction |

---

## Previous releases

- [Release notes v1.0](release_notes_v1.0.md)
