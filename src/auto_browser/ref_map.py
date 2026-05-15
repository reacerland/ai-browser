from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RefEntry:
    backend_node_id: int
    role: str
    name: str
    nth: int | None = None
    frame_id: str | None = None


class RefMap:
    def __init__(self) -> None:
        self._entries: dict[str, RefEntry] = {}
        self._next_ref: int = 1

    def add(
        self,
        ref_id: str,
        backend_node_id: int,
        role: str,
        name: str,
        nth: int | None,
        frame_id: str | None,
    ) -> None:
        self._entries[ref_id] = RefEntry(
            backend_node_id=backend_node_id,
            role=role,
            name=name,
            nth=nth,
            frame_id=frame_id,
        )

    def get(self, ref_id: str) -> RefEntry | None:
        return self._entries.get(ref_id)

    def clear(self) -> None:
        self._entries.clear()
        self._next_ref = 1

    def next_ref_num(self) -> int:
        return self._next_ref

    def set_next_ref_num(self, num: int) -> None:
        self._next_ref = num


class RoleNameTracker:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}

    def track(self, role: str, name: str, node_idx: int) -> int:
        key = (role, name)
        nth = self._counts.get(key, 0)
        self._counts[key] = nth + 1
        return nth

    def get_duplicates(self) -> dict[tuple[str, str], int]:
        return {k: v for k, v in self._counts.items() if v > 1}

    def get_actual_nth(self, role: str, name: str, occurrence: int | None = None) -> int | None:
        key = (role, name)
        count = self._counts.get(key, 0)
        if count <= 1:
            return None
        return occurrence
