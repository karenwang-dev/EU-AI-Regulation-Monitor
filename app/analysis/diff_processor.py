from pathlib import Path

import difflib

from app.analysis.diff_engine import compare_files


def _parse_unified_diff(diff_text: str) -> tuple[list[str], list[str]]:
    added_content = []
    removed_content = []

    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_content.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed_content.append(line[1:])

    return added_content, removed_content


def compare_markdown(
    old_markdown: str,
    new_markdown: str,
    old_label: str = "previous",
    new_label: str = "current",
) -> dict:
    diff_lines = difflib.unified_diff(
        old_markdown.splitlines(),
        new_markdown.splitlines(),
        fromfile=old_label,
        tofile=new_label,
        lineterm="",
    )
    diff_text = "\n".join(diff_lines)
    added_content, removed_content = _parse_unified_diff(diff_text)

    return {
        "changed": old_markdown != new_markdown,
        "added_content": added_content,
        "removed_content": removed_content,
        "diff_text": diff_text,
    }


def create_diff_result(
    source_id: str,
    old_snapshot: dict | None,
    new_snapshot: dict,
) -> dict | None:
    if old_snapshot is None:
        return None

    if old_snapshot["hash"] == new_snapshot["hash"]:
        return None

    diff_text = compare_files(
        old_snapshot["file_path"],
        new_snapshot["file_path"],
    )
    added_content, removed_content = _parse_unified_diff(diff_text)

    return {
        "source_id": source_id,
        "old_snapshot_id": old_snapshot["id"],
        "new_snapshot_id": new_snapshot["id"],
        "changed": bool(diff_text.strip()),
        "added_content": added_content,
        "removed_content": removed_content,
        "diff_text": diff_text,
    }


def read_snapshot_markdown(snapshot: dict) -> str:
    return Path(snapshot["file_path"]).read_text(encoding="utf-8")
