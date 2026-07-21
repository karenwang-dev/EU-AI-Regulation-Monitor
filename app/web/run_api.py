from fastapi import APIRouter, FastAPI, HTTPException

from app.monitors.run_store import MonitorRunStore, get_monitor_run_store


def register_run_routes(
    app: FastAPI,
    run_store: MonitorRunStore | None = None,
) -> MonitorRunStore:
    store = run_store or get_monitor_run_store()
    router = APIRouter()

    @router.get("/api/runs/{run_history_id}")
    def get_run_details(run_history_id: int):
        run = store.get_run(run_history_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    app.include_router(router)
    app.state.monitor_run_store = store
    return store
