from __future__ import annotations

from typing import Any, Sequence

USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")


def clone_usage(usage: Any) -> dict[str, int]:
    return {key: getattr(usage, key, 0) or 0 for key in USAGE_KEYS}


def merge_usage(entries: Sequence[dict[str, int]]) -> dict[str, int]:
    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError(f"merge_usage: entri bukan dict: {type(entry).__name__}: {entry!r}")

    return {key: sum(entry.get(key, 0) for entry in entries) for key in USAGE_KEYS}