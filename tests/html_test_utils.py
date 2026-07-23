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


def text_by_testid(html: str, testid: str) -> str:
    parser = _TestIdTextParser()
    parser.feed(html)
    return parser.values.get(testid, "").strip()
