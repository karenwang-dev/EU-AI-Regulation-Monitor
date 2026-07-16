from fastapi import FastAPI, HTTPException

from app.knowledge.search import (
    build_search_statistics,
    search_knowledge_items,
    suggest_knowledge_terms,
)
from app.knowledge.statistics import (
    build_knowledge_statistics,
    fetch_all_knowledge_items,
)
from app.storage.service import StorageService, _get_service


def register_knowledge_routes(
    app: FastAPI,
    storage_service: StorageService | None = None,
) -> None:
    storage = storage_service or _get_service()

    @app.get("/api/search/suggest")
    def api_search_suggest(q: str = ""):
        try:
            return suggest_knowledge_terms(
                q,
                get_items_fn=storage.get_knowledge_items,
                get_item_fn=storage.get_knowledge_item,
            )
        except Exception:
            return []

    @app.get("/api/search/statistics")
    def api_search_statistics():
        try:
            return build_search_statistics(
                get_items_fn=storage.get_knowledge_items,
                get_item_fn=storage.get_knowledge_item,
            )
        except Exception:
            return {
                "total_items": 0,
                "searchable_fields": [
                    "title",
                    "summary",
                    "requirements",
                    "actions",
                    "modules",
                    "category",
                ],
            }

    @app.get("/api/search")
    def api_search(
        q: str = "",
        category: str | None = None,
        module: str | None = None,
        limit: int = 20,
    ):
        try:
            return search_knowledge_items(
                q,
                category=category or None,
                module=module or None,
                limit=limit,
                get_items_fn=storage.get_knowledge_items,
                get_item_fn=storage.get_knowledge_item,
            )
        except Exception:
            return []

    @app.get("/api/knowledge/statistics")
    def api_knowledge_statistics():
        items = fetch_all_knowledge_items(storage)
        return build_knowledge_statistics(items)

    @app.get("/api/knowledge")
    def api_list_knowledge(
        category: str | None = None,
        module: str | None = None,
        limit: int = 50,
    ):
        return storage.get_knowledge_items(
            category=category,
            module=module,
            limit=limit,
        )

    @app.get("/api/knowledge/search")
    def api_search_knowledge(
        q: str,
        limit: int = 50,
    ):
        return storage.search_knowledge(q, limit=limit)

    @app.get("/api/knowledge/{item_id}")
    def api_get_knowledge(item_id: int):
        item = storage.get_knowledge_item(item_id)
        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Knowledge item not found",
            )
        return item
