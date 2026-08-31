from __future__ import annotations

from html.parser import HTMLParser


class _TestIdTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._active_testids: list[str] = []
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        testid = dict(attrs).get("data-testid")
        if testid:
            self._active_testids.append(testid)
            self.values.setdefault(testid, "")

    def handle_data(self, data: str) -> None:
        if not self._active_testids:
            return
        testid = self._active_testids[-1]
        self.values[testid] = self.values.get(testid, "") + data

    def handle_endtag(self, tag: str) -> None:
        if self._active_testids:
            self._active_testids.pop()


class _HtmlStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict] = []
        self._stack: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = {"tag": tag, "attrs": dict(attrs), "children": []}
        if self._stack:
            self._stack[-1]["children"].append(element)
        else:
            self.elements.append(element)
        self._stack.append(element)

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1]["tag"] == tag:
            self._stack.pop()


def text_by_testid(html: str, testid: str) -> str:
    parser = _TestIdTextParser()
    parser.feed(html)
    return parser.values.get(testid, "").strip()


def _class_list(value: str | None) -> set[str]:
    if not value:
        return set()
    return set(value.split())


def element_has_class(element: dict, class_name: str) -> bool:
    return class_name in _class_list(element.get("attrs", {}).get("class"))


def find_elements(
    elements: list[dict],
    *,
    tag: str | None = None,
    class_name: str | None = None,
    testid: str | None = None,
) -> list[dict]:
    matches: list[dict] = []

    def walk(nodes: list[dict]) -> None:
        for node in nodes:
            matched = True
            if tag is not None and node["tag"] != tag:
                matched = False
            if class_name is not None and not element_has_class(node, class_name):
                matched = False
            if testid is not None and node.get("attrs", {}).get("data-testid") != testid:
                matched = False
            if matched and (tag is not None or class_name is not None or testid is not None):
                matches.append(node)
            walk(node.get("children", []))

    walk(elements)
    return matches


def parse_html_structure(html: str) -> list[dict]:
    parser = _HtmlStructureParser()
    parser.feed(html)
    return parser.elements
