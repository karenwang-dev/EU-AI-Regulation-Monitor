from __future__ import annotations

import json
from pathlib import Path

DEMO_CONFIG_FILE = Path("config/demo.json")
DEMO_DIR = Path("data/demo")

DEFAULT_DEMO_CONFIG = {
    "enabled": False,
}

DEMO_SNAPSHOT_FILE = "demo_snapshot.json"
DEMO_ANALYSIS_FILE = "demo_analysis.json"
DEMO_REPORT_FILE = "demo_report.json"


def load_demo_config(config_file: Path | str | None = None) -> dict:
    path = Path(config_file) if config_file is not None else DEMO_CONFIG_FILE
    if not path.exists():
        return DEFAULT_DEMO_CONFIG.copy()

    with open(path, "r", encoding="utf-8") as file:
        raw_config = json.load(file)

    if not isinstance(raw_config, dict):
        return DEFAULT_DEMO_CONFIG.copy()

    config = DEFAULT_DEMO_CONFIG.copy()
    config.update(raw_config)
    config["enabled"] = bool(config.get("enabled", False))
    return config


def _load_demo_json(filename: str, demo_dir: Path | str | None = None) -> dict:
    directory = Path(demo_dir) if demo_dir is not None else DEMO_DIR
    path = directory / filename
    if not path.exists():
        raise FileNotFoundError(f"Demo file not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Demo file must contain a JSON object: {path}")

    return data


def load_demo_snapshot(demo_dir: Path | str | None = None) -> dict:
    return _load_demo_json(DEMO_SNAPSHOT_FILE, demo_dir=demo_dir)


def load_demo_analysis(demo_dir: Path | str | None = None) -> dict:
    return _load_demo_json(DEMO_ANALYSIS_FILE, demo_dir=demo_dir)


def load_demo_report(demo_dir: Path | str | None = None) -> dict:
    return _load_demo_json(DEMO_REPORT_FILE, demo_dir=demo_dir)


def build_demo_monitoring_result(
    snapshot: dict | None = None,
    analysis: dict | None = None,
    *,
    demo_dir: Path | str | None = None,
) -> dict:
    snapshot = snapshot or load_demo_snapshot(demo_dir=demo_dir)
    analysis = analysis or load_demo_analysis(demo_dir=demo_dir)

    return {
        "source_id": snapshot.get("source_id"),
        "name": snapshot.get("title"),
        "status": "analyzed",
        "snapshot_id": snapshot.get("id"),
        "diff_id": 1,
        "analysis_id": 1,
        "first_snapshot": False,
        "message": "Demo change detected and analyzed",
        "impact_level": analysis.get("impact_level"),
        "affected_modules": analysis.get("affected_modules", []),
    }


def build_demo_knowledge_item(
    snapshot: dict | None = None,
    analysis: dict | None = None,
    *,
    demo_dir: Path | str | None = None,
) -> dict:
    snapshot = snapshot or load_demo_snapshot(demo_dir=demo_dir)
    analysis = analysis or load_demo_analysis(demo_dir=demo_dir)

    return {
        "id": "demo-knowledge-1",
        "source_id": snapshot.get("source_id"),
        "snapshot_id": snapshot.get("id"),
        "title": snapshot.get("title"),
        "category": "AI Regulation",
        "modules": analysis.get("affected_modules", []),
        "summary": analysis.get("reason", ""),
        "impact_level": analysis.get("impact_level"),
        "recommended_actions": analysis.get("recommended_actions", []),
        "confidence": analysis.get("confidence"),
        "created_at": snapshot.get("created_at"),
        "url": snapshot.get("url"),
    }


def build_demo_summary(
    *,
    demo_dir: Path | str | None = None,
    config_file: Path | str | None = None,
) -> dict:
    config = load_demo_config(config_file=config_file)
    snapshot = load_demo_snapshot(demo_dir=demo_dir)
    analysis = load_demo_analysis(demo_dir=demo_dir)
    report = load_demo_report(demo_dir=demo_dir)

    return {
        "config": config,
        "monitoring_result": build_demo_monitoring_result(snapshot, analysis),
        "analysis": analysis,
        "knowledge_item": build_demo_knowledge_item(snapshot, analysis),
        "report": report,
    }
