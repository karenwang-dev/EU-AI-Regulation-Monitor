import json
import re
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.source.source_loader import (
    ALLOWED_FREQUENCIES,
    MONITORS_FILE,
    MonitorConfigError,
    validate_monitor,
)


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


class MonitorUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    keywords: list[str] | None = None
    category: str | None = None
    frequency: str | None = None
    enabled: bool | None = None


class MonitorStore:

    def __init__(self, monitors_file: Path = MONITORS_FILE):
        self.monitors_file = Path(monitors_file)

    def _read_monitors(self) -> list[dict]:
        if not self.monitors_file.exists():
            return []

        with open(self.monitors_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data.get("monitors", [])

    def _write_monitors(self, monitors: list[dict]) -> None:
        for index, monitor in enumerate(monitors):
            validate_monitor(monitor, index=index)

        self.monitors_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.monitors_file, "w", encoding="utf-8") as file:
            json.dump(
                {"monitors": monitors},
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")

    def list_monitors(self) -> list[dict]:
        return self._read_monitors()

    def get_monitor(self, monitor_id: str) -> dict | None:
        for monitor in self._read_monitors():
            if monitor["id"] == monitor_id:
                return monitor
        return None

    def create_monitor(self, payload: MonitorCreateRequest) -> dict:
        monitors = self._read_monitors()
        existing_ids = {monitor["id"] for monitor in monitors}

        monitor = {
            "id": generate_monitor_id(payload.name, existing_ids),
            "name": payload.name.strip(),
            "url": payload.url.strip(),
            "keywords": [keyword.strip() for keyword in payload.keywords if keyword.strip()],
            "category": payload.category.strip(),
            "frequency": payload.frequency.strip(),
            "enabled": payload.enabled,
        }

        try:
            validate_monitor(monitor)
        except MonitorConfigError as error:
            raise ValueError(str(error)) from error

        monitors.append(monitor)
        self._write_monitors(monitors)
        return monitor

    def update_monitor(
        self,
        monitor_id: str,
        payload: MonitorUpdateRequest,
    ) -> dict:
        monitors = self._read_monitors()
        updated_monitor = None

        for index, monitor in enumerate(monitors):
            if monitor["id"] != monitor_id:
                continue

            if payload.name is not None:
                monitor["name"] = payload.name.strip()
            if payload.url is not None:
                monitor["url"] = payload.url.strip()
            if payload.keywords is not None:
                monitor["keywords"] = [
                    keyword.strip()
                    for keyword in payload.keywords
                    if keyword.strip()
                ]
            if payload.category is not None:
                monitor["category"] = payload.category.strip()
            if payload.frequency is not None:
                monitor["frequency"] = payload.frequency.strip()
            if payload.enabled is not None:
                monitor["enabled"] = payload.enabled

            try:
                validate_monitor(monitor, index=index)
            except MonitorConfigError as error:
                raise ValueError(str(error)) from error

            updated_monitor = monitor
            break

        if updated_monitor is None:
            raise LookupError(f"Monitor not found: {monitor_id}")

        self._write_monitors(monitors)
        return updated_monitor

    def delete_monitor(self, monitor_id: str) -> dict:
        monitors = self._read_monitors()
        remaining = []
        deleted_monitor = None

        for monitor in monitors:
            if monitor["id"] == monitor_id:
                deleted_monitor = monitor
            else:
                remaining.append(monitor)

        if deleted_monitor is None:
            raise LookupError(f"Monitor not found: {monitor_id}")

        self._write_monitors(remaining)
        return deleted_monitor


def create_monitor_router(store: MonitorStore) -> APIRouter:
    router = APIRouter()

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

    return router


def register_monitor_routes(
    app: FastAPI,
    monitors_file: Path | None = None,
) -> MonitorStore:
    store = MonitorStore(monitors_file=monitors_file or MONITORS_FILE)
    app.include_router(create_monitor_router(store))
    return store
