# Changelog

All notable changes to the EU AI Regulation Monitor are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.5] - 2026-07-21 — Stable Release

### Added

- **Multi-page monitoring** — crawl homepages and discovered child pages with per-page change detection.
- **SQLite monitor repository** — `SQLiteMonitorRepository` as the canonical source of truth for monitors (`data/storage.db`).
- **Manual monitor execution** — Run button in Monitor Management; `POST /api/monitors/{id}/run`.
- **Run Details** — `GET /api/runs/{id}` and `/runs/{id}` page with page-level results.
- **Run persistence** — `monitor_runs` table stores stable historical run metadata and page results.
- **Monitor UI polish** — compact table layout, Run + More dropdown actions, execution vs change status badges.
- **Category management** — extensible categories with normalization, datalist suggestions, and `GET /api/monitors/categories`.
- **Structured run errors** — JSON error responses for failed manual runs instead of plain-text 500s.
- **About page refresh** — v1.1.5 platform overview, statistics, and roadmap.

### Changed

- Monitor configuration seed file (`config/monitors.json`) is seed-only; runtime edits persist in SQLite.
- Dashboard Recent Activity links to Run Details when a run ID is available.
- Version display reads from `VERSION` (currently `1.1.5`).

### Fixed

- Monitor More dropdown non-functional (duplicate Bootstrap JS load).
- Manual run HTTP 500 when run history path was unset.
- Category mismatch between monitor list and edit form.
- Dashboard crash when no run history exists.

### Tests

- **470** automated tests passing at release.

---

## [1.1.4] - 2026-07-21

### Added

- Unified `SQLiteMonitorRepository` with incremental seed from `config/monitors.json`.
- `monitor_execution` table for last-run metadata.
- Monitor manual run API and execution service with concurrency lock.

---

## [1.1.3] - 2026-07-20

### Added

- Multi-page change detection with page-level summaries.
- Policy A skip bug fix for unchanged child pages.

---

## [1.0.0] - 2026-07-16

### Added

- Initial production-ready internal release.
- Web dashboard, scheduler, crawler, diff engine, AI analysis, knowledge base, and weekly reports.
- Docker deployment (dashboard + scheduler services).

[1.1.5]: docs/ReleaseNotes.md
[1.0.0]: docs/release_notes_v1.0.md
