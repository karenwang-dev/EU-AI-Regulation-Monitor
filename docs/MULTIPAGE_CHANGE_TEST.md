# Multi-page Change Detection Validation

Phase v1.1.3 adds two disabled-by-default test monitors and a deterministic local test site for validating homepage and child-page change detection.

## Components

| Component | Purpose |
|-----------|---------|
| `hacker-news-change-test` | Real-world, frequently changing public site (Hacker News) |
| `local-multipage-change-test` | Deterministic local fixture served by the FastAPI app |
| `data/change_test_site.json` | Mutable state for the local test site |
| `/dev/change-test-site/*` | Local test site pages (development only) |
| `/dev/change-test-site/controls` | Development test controls UI |
| `/api/dev/change-test-site/*` | Development mutation and run endpoints |

Both test monitors set `skip_ai_analysis: true` so basic change-detection runs do not consume OpenAI credits.

## Prerequisites

1. Set development mode before starting the server (or export it in the same shell session):

   ```bash
   set APP_ENV=development
   ```

   On Linux/macOS:

   ```bash
   export APP_ENV=development
   ```

   You can also copy `.env.example` to `.env` and keep `APP_ENV=development` there when using Docker Compose.

   **Important:** `APP_ENV` is read from the process environment on each request (it is not cached at import time). After changing `APP_ENV`, restart Uvicorn/Docker if the variable was not present when the process started — otherwise export it in the same shell before launching the server. A running server picks up in-process `APP_ENV` changes without reimporting modules.

2. Confirm startup logs after launch:

   ```
   APP_ENV=development
   Development mode=True
   Development test site routes registered=True
   Development test site route: /dev/change-test-site
   ...
   ```

   If routes are registered but `Development mode=False`, endpoints return `404 {"detail":"Not found"}` until `APP_ENV` is set to `development`, `dev`, or `test`.

   ```bash
   python -m uvicorn app.web.app:app --host 127.0.0.1 --port 8080
   ```

## Local deterministic test (authoritative)

### 1. Enable the local test monitor

Open **Monitors** in the dashboard and enable **Local Multi-page Change Test**, or set `"enabled": true` for `local-multipage-change-test` in `config/monitors.json`.

### 2. Establish baseline

Run the monitor once (via scheduler, pipeline CLI, or **Run monitor now** on the test controls page).

Expected:

- Three pages crawled: homepage, Policy A, Policy B
- Baseline snapshots stored per URL
- No change records on the first run

### 3. Change only Policy A

Open [http://127.0.0.1:8080/dev/change-test-site/controls](http://127.0.0.1:8080/dev/change-test-site/controls) and click **Change Policy A**.

### 4. Run the monitor again

Click **Run monitor now** or trigger a normal monitor run.

### 5. Verify child-page-only detection

Check **Dashboard** and **Changes**:

- Today's Changes increases by one
- Changed URL ends with `/dev/change-test-site/policy-a`
- Page type badge shows **Child page**
- Homepage is **not** marked changed

### 6. Change the homepage

Click **Change homepage** on the controls page and run the monitor again.

Verify:

- Homepage change is detected
- Page type badge shows **Homepage**

### 7. Reset test data

Click **Reset test site** (confirmation required) to restore default content and versions.

## Hacker News real-world test (nondeterministic)

### 1. Enable the monitor

Enable **Hacker News Change Detection Test** (`hacker-news-change-test`).

### 2. Run baseline

Run once to store homepage and selected child pages (`/newest`, `/ask`, `/show`, `/jobs`, and up to three discussion pages).

### 3. Wait for natural changes

Hacker News content (points, comment counts, rankings, age text) changes frequently.

### 4. Run again

Review changed URLs in **Changes**. Each changed page should list its exact URL and page type.

### 5. Optional normalized mode

Set `"content_normalization_mode": "normalized"` and `"content_cleaner_profile": "hacker_news"` on the test monitor to reduce volatile ranking/age noise. Leave production monitors on `"raw"`.

### 6. Disable after testing

Keep `enabled: false` when not actively validating.

## Warnings

- Hacker News results are **nondeterministic** between runs.
- Do **not** enable short-interval crawling against Hacker News.
- Respect remote site load; keep `max_pages` low (default 8) and `max_depth` at 1.
- The **local test site** is the authoritative deterministic integration test.
- Development mutation endpoints return **404** when `APP_ENV` is not `development`, `dev`, or `test`.
- Test monitor changes appear on `/changes` with impact **Unassessed** and **Analysis: Skipped** even when AI analysis is bypassed.

## Automated tests

```bash
python -m unittest tests.test_multipage_change_detection -v
python -m unittest discover -s tests -p "test_*.py"
```

Scenarios covered:

1. Baseline crawl (3 pages, no changes)
2. Homepage-only change
3. Child-page-only change (Policy A)
4. Two child pages changed
5. Homepage + one child changed
6. New page discovered (Policy C)
7. Child page removed
8. Unchanged rerun (no false positives)
9. URL normalization (`/policy-a`, `/policy-a/`, `#fragment`)
10. Both test monitors disabled by default

## Architecture notes

- Each crawled page is stored as an independent snapshot keyed by monitor ID and URL.
- Diffs and analyses are per page, not one aggregate hash for the whole crawl.
- Run summaries include `homepage_changed`, `child_pages_changed`, `pages_added`, and `pages_removed`.
- Production monitors are unchanged; test monitors are appended to `config/monitors.json` with `"enabled": false`.
