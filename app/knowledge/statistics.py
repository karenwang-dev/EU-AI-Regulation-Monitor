from __future__ import annotations

from app.storage.service import StorageService


def fetch_all_knowledge_items(storage: StorageService) -> list[dict]:
    with storage._connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM knowledge_items
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return [storage._row_to_knowledge_item(row) for row in rows]


def build_knowledge_statistics(
    knowledge_items: list[dict],
    latest_limit: int = 10,
) -> dict:
    by_category: dict[str, int] = {}
    by_module: dict[str, int] = {}

    for item in knowledge_items:
        category = str(item.get("category", "")).strip() or "Uncategorized"
        by_category[category] = by_category.get(category, 0) + 1

        for module in item.get("modules", []):
            module_name = str(module).strip()
            if module_name:
                by_module[module_name] = by_module.get(module_name, 0) + 1

    latest_updates = [
        {
            "id": item.get("id"),
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "created_at": item.get("created_at", ""),
            "modules": item.get("modules", []),
        }
        for item in knowledge_items[:latest_limit]
    ]

    return {
        "total": len(knowledge_items),
        "by_category": by_category,
        "by_module": by_module,
        "latest_updates": latest_updates,
    }
