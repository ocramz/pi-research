#!/usr/bin/env python3
"""A stand-in for `pi --mode rpc` in x06's tests (PI_BIN). It answers the RPC calls the harness makes,
and on a prompt it really runs ./fetch.sh against the local feeds, then writes evidence.json.

FAKE_PI_MODE: honest | liar (claims feed-b) | bad_tool (calls a tool outside the allowlist) |
leaks_key (runs `env`, so the keys reach the event log) | search_spam (13 searches, no report until
the cap follow-up arrives)."""

import json
import os
import re
import subprocess
import sys
import time
import uuid

if "--version" in sys.argv:
    print("0.84.2")
    sys.exit(0)

MODE = os.environ.get("FAKE_PI_MODE", "honest")
LAST_PROMPT = ""
NB = os.environ.get("FAKE_PI_NB_DIR", "")
IDS = ["elexon", "neso-demand", "feed-a", "neso-ews", "pvlive", "feed-b", "om-era5", "om-hfc"]
calls = 0
prompts = 0


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def bash(command):
    global calls
    calls += 1
    cid = f"call_{uuid.uuid4().hex[:8]}"
    emit({"type": "tool_execution_start", "toolCallId": cid, "toolName": "bash", "args": {"command": command}})
    r = subprocess.run(["/bin/sh", "-c", command], capture_output=True, text=True)
    emit({"type": "tool_execution_end", "toolCallId": cid, "toolName": "bash",
          "result": {"content": [{"type": "text", "text": r.stdout + r.stderr}]}, "isError": r.returncode != 0})


def entry(sid, outcome, **kw):
    base = {"id": sid, "outcome": outcome, "attempt": None, "url": None, "time_field": None,
            "resolution_minutes": None, "rows_on_target_date": None, "key_or_login_seen": False, "note": "fake"}
    base.update(kw)
    return base


def search(q):
    global calls
    calls += 1
    cid = f"call_{uuid.uuid4().hex[:8]}"
    emit({"type": "tool_execution_start", "toolCallId": cid, "toolName": "web_search_tavily", "args": {"query": q}})
    emit({"type": "tool_execution_end", "toolCallId": cid, "toolName": "web_search_tavily",
          "result": {"content": [{"type": "text", "text": "no results"}]}, "isError": False})


def run_prompt(text):
    global prompts
    prompts += 1
    if MODE == "search_spam" and prompts == 1:
        emit({"type": "agent_start"})
        urls = re.findall(r"http://127\.0\.0\.1:\d+/f/[0-9a-f]+/series\.csv", text)
        if len(urls) == 2:
            bash(f"./fetch.sh feed-a '{urls[0]}'")
            bash(f"./fetch.sh feed-b '{urls[1]}'")
        for i in range(13):
            search(f"query {i}")
        time.sleep(2.0)  # the monitor sees the cap and aborts; the turn ends without a report
        emit({"type": "agent_settled"})
        return
    if MODE == "search_spam":
        text = LAST_PROMPT
    urls = re.findall(r"http://127\.0\.0\.1:\d+/f/[0-9a-f]+/series\.csv", text)
    emit({"type": "agent_start"})
    if len(urls) == 2:
        bash(f"./fetch.sh feed-a '{urls[0]}'")
        bash(f"./fetch.sh feed-b '{urls[1]}'")
    if MODE == "bad_tool":
        emit({"type": "tool_execution_start", "toolCallId": "x1", "toolName": "story", "args": {}})
        emit({"type": "tool_execution_end", "toolCallId": "x1", "toolName": "story",
              "result": {"content": [{"type": "text", "text": "no"}]}, "isError": True})
    if MODE == "leaks_key":
        bash("env")
    sources = []
    for sid in IDS:
        if sid == "feed-a" and urls:
            sources.append(entry(sid, "retrieved", attempt=1, url=urls[0], time_field="time",
                                 resolution_minutes=30, rows_on_target_date=48))
        elif sid == "feed-b" and urls:
            if MODE == "liar":
                sources.append(entry(sid, "retrieved", attempt=1, url=urls[1], time_field="time",
                                     resolution_minutes=30, rows_on_target_date=48))
            else:
                sources.append(entry(sid, "key_required", attempt=1, url=urls[1], key_or_login_seen=True))
        else:
            sources.append(entry(sid, "not_tried"))
    with open("evidence.json", "w") as f:
        json.dump({"schema": "x06-evidence/1", "sources": sources}, f)
    emit({"type": "agent_settled"})


for line in sys.stdin:
    try:
        cmd = json.loads(line)
    except ValueError:
        continue
    kind, cid = cmd.get("type"), cmd.get("id")
    if kind == "get_commands":
        cmds = [{"name": "nb-python", "source": "extension", "sourceInfo": {"baseDir": NB}},
                {"name": "nb", "source": "extension", "sourceInfo": {"baseDir": NB}},
                {"name": "llama", "source": "extension", "sourceInfo": {}}]
        emit({"id": cid, "type": "response", "command": kind, "success": True, "data": {"commands": cmds}})
    elif kind == "get_state":
        emit({"id": cid, "type": "response", "command": kind, "success": True,
              "data": {"model": {"provider": "openrouter", "id": "deepseek/deepseek-v4-flash"},
                       "thinkingLevel": "high", "isStreaming": False}})
    elif kind == "get_available_thinking_levels":
        emit({"id": cid, "type": "response", "command": kind, "success": True, "data": {"levels": ["off", "high", "xhigh"]}})
    elif kind == "get_session_stats":
        emit({"id": cid, "type": "response", "command": kind, "success": True,
              "data": {"cost": 0.0, "tokens": {"total": 0}, "toolCalls": calls}})
    elif kind == "prompt":
        emit({"id": cid, "type": "response", "command": kind, "success": True})
        if prompts == 0:
            LAST_PROMPT = cmd.get("message", "")
        run_prompt(cmd.get("message", ""))
    else:
        emit({"id": cid, "type": "response", "command": kind, "success": True})
