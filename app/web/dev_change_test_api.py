from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.environment import is_development
from app.dev.change_test_site import (
    ChangeTestSiteError,
    LOCAL_TEST_MONITOR_ID,
    build_local_test_monitor_urls,
    get_public_status,
    load_state,
    render_homepage_html,
    render_page_html,
    reset_state,
    set_policy_c_enabled,
    update_page,
)
from app.source.source_loader import load_monitors


class ChangeTestSiteUpdateRequest(BaseModel):
    text: str = Field(min_length=1)


def _require_development() -> None:
    if not is_development():
        raise HTTPException(status_code=404, detail="Not found")


def _state_file_from_request(request: Request) -> Path | None:
    override = getattr(request.app.state, "change_test_site_file", None)
    return Path(override) if override else None


def register_change_test_site_routes(app) -> list[str]:
    router = APIRouter()
    registered_paths: list[str] = []

    @router.get("/dev/change-test-site")
    def change_test_site_home(request: Request):
        _require_development()
        from fastapi.responses import HTMLResponse

        html = render_homepage_html(load_state(_state_file_from_request(request)))
        return HTMLResponse(content=html)

    @router.get("/dev/change-test-site/policy-a")
    def change_test_site_policy_a(request: Request):
        _require_development()
        from fastapi.responses import HTMLResponse

        html = render_page_html(
            "/dev/change-test-site/policy-a",
            state_file=_state_file_from_request(request),
        )
        return HTMLResponse(content=html)

    @router.get("/dev/change-test-site/policy-b")
    def change_test_site_policy_b(request: Request):
        _require_development()
        from fastapi.responses import HTMLResponse

        html = render_page_html(
            "/dev/change-test-site/policy-b",
            state_file=_state_file_from_request(request),
        )
        return HTMLResponse(content=html)

    @router.get("/dev/change-test-site/policy-c")
    def change_test_site_policy_c(request: Request):
        _require_development()
        from fastapi.responses import HTMLResponse

        try:
            html = render_page_html(
                "/dev/change-test-site/policy-c",
                state_file=_state_file_from_request(request),
            )
        except ChangeTestSiteError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(content=html)

    @router.get("/dev/change-test-site/status")
    def change_test_site_status(request: Request):
        _require_development()
        return get_public_status(_state_file_from_request(request))

    @router.post("/api/dev/change-test-site/homepage/change")
    def change_homepage(payload: ChangeTestSiteUpdateRequest, request: Request):
        _require_development()
        return update_page(
            "homepage",
            text=payload.text,
            state_file=_state_file_from_request(request),
        )

    @router.post("/api/dev/change-test-site/policy-a/change")
    def change_policy_a(payload: ChangeTestSiteUpdateRequest, request: Request):
        _require_development()
        return update_page(
            "policy_a",
            text=payload.text,
            state_file=_state_file_from_request(request),
        )

    @router.post("/api/dev/change-test-site/policy-b/change")
    def change_policy_b(payload: ChangeTestSiteUpdateRequest, request: Request):
        _require_development()
        return update_page(
            "policy_b",
            text=payload.text,
            state_file=_state_file_from_request(request),
        )

    @router.post("/api/dev/change-test-site/policy-c/add")
    def add_policy_c(request: Request):
        _require_development()
        return set_policy_c_enabled(True, state_file=_state_file_from_request(request))

    @router.post("/api/dev/change-test-site/policy-c/remove")
    def remove_policy_c(request: Request):
        _require_development()
        return set_policy_c_enabled(False, state_file=_state_file_from_request(request))

    @router.get("/dev/change-test-site/controls")
    def change_test_site_controls(request: Request):
        _require_development()
        from fastapi.responses import HTMLResponse
        from fastapi.templating import Jinja2Templates

        templates = Jinja2Templates(
            directory=str(Path(__file__).resolve().parent / "templates")
        )
        status = get_public_status(_state_file_from_request(request))
        return templates.TemplateResponse(
            request,
            "change_test_controls.html",
            {
                "title": "Change Test Controls",
                "active_page": "monitors",
                "status": status,
                "monitor_id": LOCAL_TEST_MONITOR_ID,
            },
        )

    @router.post("/api/dev/change-test-site/reset")
    def reset_change_test_site(request: Request):
        _require_development()
        return reset_state(state_file=_state_file_from_request(request))

    @router.post("/api/dev/change-test-site/run-monitor")
    def run_local_test_monitor(request: Request):
        _require_development()
        from app.monitors.execution import MonitorExecutionService

        monitor = next(
            (
                item
                for item in load_monitors()
                if item.get("id") == LOCAL_TEST_MONITOR_ID
            ),
            None,
        )
        if monitor is None:
            raise HTTPException(status_code=404, detail="Local test monitor not configured.")

        runner = getattr(request.app.state, "monitor_execution_service", None)
        if runner is None:
            runner = MonitorExecutionService()

        return runner.run_monitor(
            LOCAL_TEST_MONITOR_ID,
            triggered_by="manual_ui_dev_controls",
        )

    app.include_router(router)

    for route in router.routes:
        path = getattr(route, "path", None)
        if path:
            registered_paths.append(path)

    app.state.change_test_site_routes_registered = True
    app.state.change_test_site_route_paths = registered_paths
    return registered_paths
