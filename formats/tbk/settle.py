"""Replay a TBK the way ToolBook opens one.

The file is read from beginning to end. A later record with the same
page id replaces the earlier one. A later record marked deleted removes
that page. The viewer is not shown the log, only what remains.
"""

from __future__ import annotations


def settle_pages(records: list[dict]) -> list[dict]:
    order: list[str] = []
    latest: dict[str, dict] = {}
    for record in records:
        key = str(record.get("id") or "")
        if not key:
            continue
        if record.get("deleted"):
            latest.pop(key, None)
            if key in order:
                order.remove(key)
            continue
        if key not in latest:
            order.append(key)
        latest[key] = record
    return [latest[key] for key in order if key in latest]
