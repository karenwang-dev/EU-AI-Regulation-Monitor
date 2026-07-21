import re
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.paths import PROJECT_ROOT
from app.monitors.execution import (
    MonitorAlreadyRunningError,
    MonitorExecutionService,
    MonitorRunPersistenceError,
)
from app.monitors.repository import MonitorRepository, get_monitor_repository
from app.monitors.run_store import get_monitor_run_store
from app.run_history import RUN_HISTORY_FILE
from app.source.source_loader import MonitorConfigError, normalize_legacy_source

logger = get_logger(__name__)


def generate_monitor_id(name: str, existing_ids: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not base:
        base = "monitor"

    candidate = base
    counter = 2
    while candidate in existing_ids:
        candidate = f"{base}_{counter}"
        counter += 1

    return candidate


class MonitorCreateRequest(BaseModel):
    name: str
    url: str
    keywords: list[str]
    category: str
    frequency: str
    enabled: bool = True
    crawl_mode: str = "single"
    max_depth: int = 0
    max_pages: int = 1


class MonitorUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    keywords: list[str] | None = None
    category: str | None = None
    frequency: str | None = None
    enabled: bool | None = None
    crawl_mode: str | None = None
    max_depth: int | None = None
    max_pages: int | None = None


class MonitorRunResponse(BaseModel):
    monitor_id: str
    status: str
    change_status: str
    execution_status: str
    pages_checked: int
    pages_changed: int
    homepage_changed: bool
    child_pages_changed: int
    snapshot_id: int | None = None
    diff_id: int | None = None
    started_at: str
    finished_at: str
    error: str | None = None
    run_history_id: int
    duration_ms: int
    run_history_summary_id: str | None = None


class MonitorRunErrorDetail(BaseModel):
    detail: str
    monitor_id: str
    error_code: str


class MonitorStore:
    def __init__(self, repository: MonitorRepository | None = None):
        self.repository = repository or get_monitor_repository()

    def list_monitors(self) -> list[dict]:
        return self.repository.list_all()

    def get_monitor(self, monitor_id: str) -> dict | None:
        return self.repository.get_by_id(monitor_id)

    def create_monitor(self, payload: MonitorCreateRequest) -> dict:
        existing_ids = {
            monitor["id"] for monitor in self.repository.list_all()
        }

        monitor = {
            "id": generate_monitor_id(payload.name, existing_ids),
            "name": payload.name.strip(),
            "url": payload.url.strip(),
            "keywords": [
                keyword.strip()
                for keyword in payload.keywords
                if keyword.strip()
            ],
            "category": payload.category.strip(),
            "frequency": payload.frequency.strip(),
            "enabled": payload.enabled,
            "crawl_mode": payload.crawl_mode.strip(),
            "max_depth": payload.max_depth,
            "max_pages": payload.max_pages,
        }

        try:
            return self.repository.create(monitor)
        except MonitorConfigError as error:
            raise ValueError(str(error)) from error

    def update_monitor(
        self,
        monitor_id: str,
        payload: MonitorUpdateRequest,
    ) -> dict:
        updates = {
            key: value
            for key, value in payload.model_dump().items()
            if value is not None
        }
        if "name" in updates:
            updates["name"] = updates["name"].strip()
        if "url" in updates:
            updates["url"] = updates["url"].strip()
        if "keywords" in updates:
            updates["keywords"] = [
                keyword.strip()
                for keyword in updates["keywords"]
                if keyword.strip()
            ]
        if "category" in updates:
            updates["category"] = updates["category"].strip()
        if "frequency" in updates:
            updates["frequency"] = updates["frequency"].strip()
        if "crawl_mode" in updates:
            updates["crawl_mode"] = updates["crawl_mode"].strip()

        try:
            return self.repository.update(monitor_id, updates)
        except LookupError:
            raise
        except MonitorConfigError as error:
            raise ValueError(str(error)) from error

    def delete_monitor(self, monitor_id: str) -> dict:
        return self.repository.delete(monitor_id)


def create_monitor_router(
    store: MonitorStore,
    execution_service: MonitorExecutionService | None = None,
) -> APIRouter:
    router = APIRouter()
    runner = execution_service or MonitorExecutionService(repository=store.repository)

    @router.get("/api/monitors")
    def get_monitors():
        return store.list_monitors()

    @router.post("/api/monitors", status_code=201)
    def create_monitor(payload: MonitorCreateRequest):
        try:
            return store.create_monitor(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.put("/api/monitors/{monitor_id}")
    def update_monitor(monitor_id: str, payload: MonitorUpdateRequest):
        if not any(
            value is not None
            for value in payload.model_dump().values()
        ):
            raise HTTPException(
                status_code=400,
                detail="At least one field must be provided for update.",
            )

        try:
            return store.update_monitor(monitor_id, payload)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.delete("/api/monitors/{monitor_id}")
    def delete_monitor(monitor_id: str):
        try:
            deleted = store.delete_monitor(monitor_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        return {
            "message": "Monitor removed from active monitoring list.",
            "monitor": deleted,
        }

    @router.post(
        "/api/monitors/{monitor_id}/run",
        response_model=MonitorRunResponse,
        responses={
            409: {"model": MonitorRunErrorDetail},
            500: {"model": MonitorRunErrorDetail},
        },
    )
    def run_monitor(monitor_id: str):
        try:
            return runner.run_monitor(monitor_id, triggered_by="manual_ui")
        except MonitorAlreadyRunningError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "Monitor is already running",
                    "monitor_id": monitor_id,
                    "error_code": "MONITOR_ALREADY_RUNNING",
                },
            ) from error
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except MonitorRunPersistenceError as error:
            logger.exception(
                "Monitor run persistence failed: monitor_id=%s",
                monitor_id,
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "detail": str(error),
                    "monitor_id": monitor_id,
                    "error_code": "RUN_PERSISTENCE_FAILED",
                },
            ) from error
        except Exception as error:
            logger.exception(
                "Monitor run failed: monitor_id=%s",
                monitor_id,
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "detail": "Monitor run failed",
                    "monitor_id": monitor_id,
                    "error_code": "RUN_EXECUTION_FAILED",
                },
            ) from error

    return router


def register_monitor_routes(
    app: FastAPI,
    monitors_file: Path | None = None,
    monitors_repository: MonitorRepository | None = None,
    execution_service: MonitorExecutionService | None = None,
) -> MonitorStore:
    if monitors_repository is not None:
        repository = monitors_repository
    elif monitors_file is not None:
        repository = get_monitor_repository(seed_file=monitors_file)
    else:
        repository = get_monitor_repository()

    store = MonitorStore(repository=repository)
    runner = execution_service or MonitorExecutionService(
        repository=repository,
        history_file=(PROJECT_ROOT / RUN_HISTORY_FILE).resolve(),
        run_store=get_monitor_run_store(db_path=repository.db_path),
    )
    app.include_router(create_monitor_router(store, execution_service=runner))
    app.state.monitor_repository = repository
    app.state.monitor_execution_service = runner
    return store
