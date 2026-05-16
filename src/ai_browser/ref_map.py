from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RefEntry:
    role: str
    name: str
    nth: int


class RefMap:
    def __init__(self) -> None:
        self._entries: dict[str, RefEntry] = {}

    def add(self, ref_id: str, role: str, name: str, nth: int) -> None:
        self._entries[ref_id] = RefEntry(role=role, name=name, nth=nth)

    def get(self, ref_id: str) -> RefEntry | None:
        return self._entries.get(ref_id)

    def clear(self) -> None:
        self._entries.clear()


# Matches lines like: - button "Submit" [ref=e1]
# or: - textbox [ref=e5]
# or: - link "foo/bar" [ref=e10]
_LINE_RE = re.compile(
    r'^\s*-\s+'           # list item prefix with indentation
    r'(\w+)'              # role (group 1)
    r'(?:\s+"([^"]*)")?'  # optional "name" (group 2)
    r'.*?\[ref=(e\d+)\]'  # [ref=eN] (group 3)
)


def parse_snapshot(yaml_text: str) -> RefMap:
    ref_map = RefMap()
    if not yaml_text:
        return ref_map

    # Track occurrences of (role, name) for nth calculation
    counts: dict[tuple[str, str], int] = {}

    for line in yaml_text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        role = m.group(1)
        name = m.group(2) or ""
        ref_id = m.group(3)
        key = (role, name)
        nth = counts.get(key, 0)
        counts[key] = nth + 1
        ref_map.add(ref_id, role, name, nth)

    return ref_map
