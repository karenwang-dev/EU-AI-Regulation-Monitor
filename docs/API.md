# REST API Reference — v1.1.5 Stable

Base URL (local): `http://localhost:8080`

All JSON APIs return `application/json` unless noted. HTML routes return `text/html`.

---

## Health

### `GET /health`

Operational health check.

**Response 200 / 503:**

```json
{
  "status": "ok",
  "timestamp": "2026-07-21T12:00:00",
  "database": "ok",
  "scheduler": "ok"
}
```

---

## Monitors

Canonical monitor data is served from `SQLiteMonitorRepository`.

### `GET /api/monitors`

List all monitors with execution metadata.

**Response:** array of monitor objects including `id`, `name`, `url`, `keywords`, `category`, `frequency`, `crawl_mode`, `enabled`, `last_run_at`, `last_change_status`, `last_run_history_id`, `last_pages_changed`, etc.

### `GET /api/monitors/categories`

Category suggestions for create/edit forms.

**Query parameters:**

| Name | Type | Description |
|------|------|-------------|
| `current` | string | Optional monitor category to include even if not in built-in list |

**Response:**

```json
{
  "categories": [
    { "value": "national_regulation", "label": "National Regulation" },
    { "value": "eu_regulation", "label": "EU Regulation" }
  ]
}
```

### `POST /api/monitors`

Create a monitor. Returns **201**.

**Request body:**

```json
{
  "name": "Example Monitor",
  "url": "https://example.com/regulation",
  "keywords": ["regulation", "compliance"],
  "category": "National Regulation",
  "frequency": "daily",
  "enabled": true,
  "crawl_mode": "single",
  "max_depth": 0,
  "max_pages": 1
}
```

Category is normalized on save (e.g. `"National Regulation"` → `national_regulation`).

**Errors:** `400` validation error (e.g. invalid category, bad URL).

### `PUT /api/monitors/{monitor_id}`

Partial update. At least one field required.

**Errors:** `404` monitor not found, `400` validation error.

### `DELETE /api/monitors/{monitor_id}`

Remove monitor from active list.

**Response:**

```json
{
  "message": "Monitor removed from active monitoring list.",
  "monitor": { }
}
```

### `POST /api/monitors/{monitor_id}/run`

Execute a monitor manually from the UI.

**Response 200:**

```json
{
  "monitor_id": "eu_ai_act",
  "status": "unchanged",
  "change_status": "unchanged",
  "execution_status": "success",
  "pages_checked": 3,
  "pages_changed": 0,
  "homepage_changed": false,
  "child_pages_changed": 0,
  "snapshot_id": 46,
  "diff_id": null,
  "started_at": "2026-07-21T12:00:00",
  "finished_at": "2026-07-21T12:00:02",
  "error": null,
  "run_history_id": 7,
  "duration_ms": 2000,
  "run_history_summary_id": "48"
}
```

**Errors:**

| Status | Condition |
|--------|-----------|
| `409` | Monitor already running |
| `404` | Monitor not found |
| `500` | Structured JSON: `{ "detail": "...", "monitor_id": "...", "error_code": "RUN_PERSISTENCE_FAILED" }` |

---

## Runs

### `GET /api/runs/{run_history_id}`

Fetch a persisted run record.

**Response 200:**

```json
{
  "run_history_id": 7,
  "monitor_id": "eu_ai_act",
  "monitor_name": "EU AI Act Portal",
  "triggered_by": "manual_ui",
  "execution_status": "success",
  "change_status": "changed",
  "started_at": "2026-07-21T10:00:00",
  "finished_at": "2026-07-21T10:00:02",
  "duration_ms": 2400,
  "pages_checked": 3,
  "pages_changed": 1,
  "homepage_changed": false,
  "child_pages_changed": 1,
  "pages_added": 0,
  "pages_removed": 0,
  "pages_failed": 0,
  "page_results": [
    {
      "url": "https://example.com/policy-a",
      "page_title": "Policy A",
      "page_type": "child",
      "status": "changed",
      "snapshot_id": 10,
      "previous_snapshot_id": 9,
      "diff_id": 5,
      "content_hash": "abc123",
      "error": null
    }
  ],
  "page_details_available": true,
  "legacy": false
}
```

**Errors:** `404` run not found.

### HTML: `GET /runs/{run_history_id}`

Run Details page with summary cards and page-results table.

---

## Changes & analysis

### `GET /api/changes`

List detected changes (used by Changes page).

### `GET /api/diff/{diff_id}`

Diff payload for a change.

### `GET /api/analysis/{analysis_id}`

AI analysis record.

### HTML: `GET /detail/{diff_id}`

Change detail page.

---

## Knowledge & search

### `GET /api/knowledge`

List knowledge items. Supports `category`, `module`, pagination query params.

### `GET /api/knowledge/{item_id}`

Single knowledge item.

### `GET /api/knowledge/statistics`

Aggregated knowledge statistics.

### `GET /api/search`

Full-text search across knowledge base.

**Query:** `q`, optional `category`, `module`.

### `GET /api/search/suggest`

Search autocomplete suggestions.

---

## Reports

### `GET /api/reports`

List generated reports.

### `GET /api/reports/latest`

Most recent report.

### `GET /api/reports/{report_id}`

Single report JSON.

### `POST /api/reports/generate`

Generate a weekly report on demand.

### `POST /api/reports/{report_id}/email/send`

Send report by email.

### `POST /api/reports/email/test`

Send test email with current SMTP settings.

---

## Email settings

### `GET /api/email/settings`

Current SMTP configuration (password masked).

### `PUT /api/email/settings`

Update SMTP settings.

### `POST /api/email/settings/test`

Send test message.

---

## HTML pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard |
| `/monitors` | Monitor Management |
| `/changes` | Change list |
| `/knowledge` | Knowledge Base |
| `/knowledge/statistics` | Knowledge statistics |
| `/knowledge/{item_id}` | Knowledge detail |
| `/reports` | Reports |
| `/insights` | Compliance insights |
| `/about` | Platform overview (v1.1.5) |
| `/runs/{id}` | Run Details |

---

## Authentication

The dashboard is designed for **trusted internal networks**. No built-in authentication layer is included in v1.1.5. Deploy behind your organization's network controls or reverse proxy if exposing beyond localhost.

---

## Related documents

- [Architecture.md](Architecture.md)
- [Database.md](Database.md)
- [DeveloperGuide.md](DeveloperGuide.md)
