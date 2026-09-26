"""Reading a pidrive run directory's `events.jsonl` (plain or gzipped): tool calls, curl write-outs,
searches, cost."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def iter_events(path: Path) -> Iterator[dict]:
    """Records split on b"\\n" only (U+2028 is not a break). Unparseable lines are skipped."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        for raw in f:
            line = raw.rstrip(b"\n").rstrip(b"\r")
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict):
                yield ev


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def tool_calls(events: list[dict]) -> list[dict[str, Any]]:
    """start/end paired on toolCallId, in start order."""
    calls: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for ev in events:
        kind = ev.get("type")
        cid = ev.get("toolCallId")
        if kind == "tool_execution_start" and cid:
            calls[cid] = {"id": cid, "name": ev.get("toolName"), "args": ev.get("args"), "result": None,
                          "is_error": None}
            order.append(cid)
        elif kind == "tool_execution_end" and cid:
            call = calls.setdefault(cid, {"id": cid, "name": ev.get("toolName"), "args": None})
            if cid not in order:
                order.append(cid)
            res = ev.get("result")
            call["result"] = _text(res.get("content")) if isinstance(res, dict) else str(res or "")
            call["is_error"] = bool(ev.get("isError"))
    return [calls[c] for c in order]


def curl_writeouts(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every curl `%{json}` object printed in a bash result: a line that parses as a JSON object
    with `filename_effective`."""
    out = []
    for call in calls:
        if call.get("name") != "bash" or not call.get("result"):
            continue
        for line in call["result"].splitlines():
            line = line.strip()
            if not (line.startswith("{") and "filename_effective" in line):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                out.append({"call": call["id"], "command": (call.get("args") or {}).get("command"), **obj})
    return out


def search_count(events: list[dict]) -> int:
    return sum(1 for ev in events if ev.get("type") == "tool_execution_start"
               and ev.get("toolName") == "web_search_tavily")


def extension_errors(events: list[dict]) -> list[dict]:
    return [ev for ev in events if ev.get("type") == "extension_error"]


def events_cost(events: list[dict]) -> float:
    """Σ of message_end usage cost: the session's spend, readable after pi has stopped (deviation 1)."""
    total = 0.0
    for ev in events:
        if ev.get("type") == "message_end":
            usage = (ev.get("message") or {}).get("usage") or {}
            c = (usage.get("cost") or {}).get("total")
            if isinstance(c, (int, float)):
                total += float(c)
        elif ev.get("type") == "compaction_end":
            usage = (ev.get("result") or {}).get("usage") or {}
            c = (usage.get("cost") or {}).get("total")
            if isinstance(c, (int, float)):
                total += float(c)
    return total
