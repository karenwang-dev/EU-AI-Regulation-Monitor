from __future__ import annotations

import json
from pathlib import Path

from app.core.paths import CHANGE_TEST_SITE_FILE

DEFAULT_STATE_FILE = CHANGE_TEST_SITE_FILE
LOCAL_TEST_MONITOR_ID = "local-multipage-change-test"

DEFAULT_STATE = {
    "homepage": {
        "version": 1,
        "text": "Initial homepage content",
    },
    "policy_a": {
        "version": 1,
        "text": "Devices must support requirement A.",
    },
    "policy_b": {
        "version": 1,
        "text": "Devices must support requirement B.",
    },
    "policy_c_enabled": False,
    "policy_c": {
        "version": 1,
        "text": "Devices must support requirement C.",
    },
}


class ChangeTestSiteError(ValueError):
    pass


def _state_path(state_file: Path | str | None = None) -> Path:
    return Path(state_file) if state_file is not None else DEFAULT_STATE_FILE


def load_state(state_file: Path | str | None = None) -> dict:
    path = _state_path(state_file)
    if not path.exists():
        return reset_state(state_file=path, persist=True)

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ChangeTestSiteError("Change test site state must be a JSON object.")
    return data


def save_state(state: dict, *, state_file: Path | str | None = None) -> dict:
    path = _state_path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def reset_state(*, state_file: Path | str | None = None, persist: bool = True) -> dict:
    state = json.loads(json.dumps(DEFAULT_STATE))
    if persist:
        save_state(state, state_file=state_file)
    return state


def update_page(
    page_key: str,
    *,
    text: str | None = None,
    state_file: Path | str | None = None,
) -> dict:
    allowed = {"homepage", "policy_a", "policy_b", "policy_c"}
    normalized_key = str(page_key or "").strip().lower().replace("-", "_")
    if normalized_key not in allowed:
        raise ChangeTestSiteError(f"Unsupported page key: {page_key}")

    state = load_state(state_file)
    page = state.setdefault(normalized_key, {"version": 0, "text": ""})
    page["version"] = int(page.get("version", 0)) + 1
    if text is not None:
        page["text"] = str(text).strip()
    return save_state(state, state_file=state_file)


def set_policy_c_enabled(
    enabled: bool,
    *,
    state_file: Path | str | None = None,
) -> dict:
    state = load_state(state_file)
    state["policy_c_enabled"] = bool(enabled)
    if enabled and int(state.get("policy_c", {}).get("version", 0)) < 1:
        state["policy_c"] = {"version": 1, "text": "Devices must support requirement C."}
    return save_state(state, state_file=state_file)


def get_public_status(state_file: Path | str | None = None) -> dict:
    state = load_state(state_file)
    return {
        "homepage_version": state["homepage"]["version"],
        "policy_a_version": state["policy_a"]["version"],
        "policy_b_version": state["policy_b"]["version"],
        "policy_c_enabled": bool(state.get("policy_c_enabled", False)),
        "policy_c_version": state.get("policy_c", {}).get("version", 0),
    }


def _page_links(state: dict) -> list[tuple[str, str]]:
    links = [
        ("Policy A", "/dev/change-test-site/policy-a"),
        ("Policy B", "/dev/change-test-site/policy-b"),
    ]
    if state.get("policy_c_enabled"):
        links.append(("Policy C", "/dev/change-test-site/policy-c"))
    return links


def render_homepage_html(state: dict) -> str:
    links = "\n".join(
        f'    <li><a href="{href}">{label}</a></li>'
        for label, href in _page_links(state)
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><title>Change Detection Test Site</title></head>
<body>
  <h1>Change Detection Test Site</h1>
  <p>Homepage version: {state["homepage"]["version"]}</p>
  <p>Last test note: {state["homepage"]["text"]}</p>
  <ul>
{links}
  </ul>
</body>
</html>"""


def render_policy_html(title: str, page: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><title>{title}</title></head>
<body>
  <h1>{title}</h1>
  <p>Version: {page["version"]}</p>
  <p>Requirement: {page["text"]}</p>
</body>
</html>"""


def render_page_html(path: str, *, state_file: Path | str | None = None) -> str:
    state = load_state(state_file)
    normalized = str(path or "/").rstrip("/") or "/dev/change-test-site"

    if normalized.endswith("/policy-a"):
        return render_policy_html("Policy A", state["policy_a"])
    if normalized.endswith("/policy-b"):
        return render_policy_html("Policy B", state["policy_b"])
    if normalized.endswith("/policy-c"):
        if not state.get("policy_c_enabled"):
            raise ChangeTestSiteError("Policy C is not enabled.")
        return render_policy_html("Policy C", state["policy_c"])
    return render_homepage_html(state)


def render_page_markdown(path: str, *, state_file: Path | str | None = None) -> str:
    html = render_page_html(path, state_file=state_file)
    from app.crawler.http_fetcher import html_to_markdown

    return html_to_markdown(html)


def resolve_page_metadata(path: str, *, state_file: Path | str | None = None) -> dict:
    state = load_state(state_file)
    normalized = str(path or "/").rstrip("/") or "/dev/change-test-site"

    if normalized.endswith("/policy-a"):
        return {"title": "Policy A", "page_key": "policy_a", "version": state["policy_a"]["version"]}
    if normalized.endswith("/policy-b"):
        return {"title": "Policy B", "page_key": "policy_b", "version": state["policy_b"]["version"]}
    if normalized.endswith("/policy-c"):
        return {"title": "Policy C", "page_key": "policy_c", "version": state["policy_c"]["version"]}
    return {"title": "Change Detection Test Site", "page_key": "homepage", "version": state["homepage"]["version"]}


def build_local_test_monitor_urls(base_url: str, monitor: dict) -> list[dict]:
    from urllib.parse import urljoin

    state_file = monitor.get("_change_test_state_file")
    base = base_url.rstrip("/")
    if base.endswith("/dev/change-test-site"):
        root = base
    else:
        root = urljoin(base + "/", "dev/change-test-site")
    paths = [
        ("", 0),
        ("/policy-a", 1),
        ("/policy-b", 1),
    ]
    state = load_state(state_file)
    if state.get("policy_c_enabled"):
        paths.append(("/policy-c", 1))

    max_pages = int(monitor.get("max_pages", len(paths)))
    urls: list[dict] = []
    for suffix, depth in paths[:max_pages]:
        page_url = root if not suffix else f"{root.rstrip('/')}{suffix}"
        urls.append(
            {
                "url": page_url,
                "title": suffix.replace("/", "").replace("-", " ").title() or "Homepage",
                "depth": depth,
            }
        )
    return urls
