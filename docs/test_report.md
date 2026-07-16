# Test Report — v1.0.0

**Product:** AI Regulation Monitor  
**Version:** 1.0.0  
**Date:** 2026-07-16  
**Environment:** Python 3.11, Windows

## Summary

| Metric | Value |
|--------|-------|
| **Total tests** | 261 |
| **Passed** | 261 |
| **Failed** | 0 |
| **Skipped** | 0 |
| **Result** | **PASS** |
| **Duration** | ~55 seconds |

## Test Command

```bash
python -m pytest
```

Verbose output:

```bash
python -m pytest -v
```

Single module:

```bash
python -m pytest tests/test_pipeline.py -v
```

## Test Suites

| Area | Test Files |
|------|------------|
| Pipeline & scheduler | `test_pipeline.py`, `test_scheduler.py`, `test_scheduler_status.py`, `test_report_scheduler.py` |
| Crawler | `test_crawler_service.py`, `test_crawl_cache.py`, `test_url_resolver.py`, `test_url_ranker.py`, `test_link_discovery.py`, `test_pdf_handler.py` |
| AI analysis | `test_impact_analyzer.py`, `test_regulation_extractor.py` |
| Storage | `test_storage_service.py`, `test_diff_processor.py`, `test_knowledge_storage.py` |
| Knowledge | `test_knowledge_builder.py`, `test_knowledge_search.py`, `test_knowledge_relationship.py`, `test_knowledge_intelligence.py`, `test_knowledge_helper.py` |
| Reports | `test_report_builder.py`, `test_report_ai_generator.py`, `test_report_web.py`, `test_report_email.py` |
| Web dashboard | `test_api.py`, `test_dashboard_web.py`, `test_monitor_api.py`, `test_knowledge_web.py`, `test_insights_web.py`, `test_search_api.py`, `test_about_page.py`, `test_health.py` |
| Operations | `test_logging.py`, `test_config_validator.py`, `test_notification.py` |
| Sources | `test_source_loader.py`, `test_source_helper.py` |

**Total test files:** 37

## Release Criteria

- [x] All unit and integration tests pass
- [x] No changes to crawler, AI analyzer, pipeline, knowledge, report generation, or database schema in this release phase
- [x] Configuration validation and health checks covered by tests
- [x] Docker deployment files present (`Dockerfile`, `docker-compose.yml`)
- [x] Documentation complete (`README.md`, `docs/`)

## Notes

- Tests use temporary directories and mocks for external APIs (OpenAI, Firecrawl, SMTP) where applicable.
- FastAPI `on_event("startup")` deprecation warnings are expected and do not affect test results.
- Log file handlers may produce Windows file-lock warnings during test teardown; tests use `reset_logging_config()` and `ignore_cleanup_errors=True` where needed.

## Related Documents

- [Release Notes v1.0](release_notes_v1.0.md)
- [Deployment Guide](deployment.md)
