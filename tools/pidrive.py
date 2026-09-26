#!/usr/bin/env python3
"""Drive a pi session through its RPC mode, from shell calls that each exit.

`pi --mode rpc` reads JSON commands on stdin and streams JSON events on stdout
(docs/rpc.md in the pi package). Something has to hold that process between
one shell call and the next: `serve` runs in the background, owns pi's pipes
and exchanges everything through a run directory. The other subcommands are
short-lived clients of that directory.

    RUN/cmds.jsonl      commands the clients append; serve forwards each line to pi
    RUN/events.jsonl    pi's stdout as received, plus serve's own pidrive_* notes
    RUN/transcript.log  the same, rendered for `tail -f`
    RUN/stderr.log      pi's stderr
    RUN/turn.json       where the last send/wait/ui stopped reading events.jsonl
    RUN/exit_code       pi's exit status, once it has exited

Start a session in the background. The model is the submodule's pin, never one
spelled out here, and pi-notebook-py needs the Python 3.12 shim on PATH:

    set -a; . ./.env; set +a
    PATH=$PWD/.cache/python-shim:$PATH pi-agent-experiments/shared/with-versions.sh \\
        python3 tools/pidrive.py serve RUN --cwd WORKDIR -- --session-dir RUN/sessions &

Then drive it, one turn per call:

    tools/pidrive.py send RUN "Create a story titled 'Demo'"
    tools/pidrive.py ui RUN <dialog id> --value Merge
    tools/pidrive.py wait RUN
    tools/pidrive.py cmd RUN '{"type": "get_session_stats"}'
    tools/pidrive.py stop RUN

send, wait and ui print what happened and exit 0 once pi is idle, 1 if pi
rejected the prompt, 2 while a dialog waits for `ui`, 3 if pi is not running,
and 124 if pi is still working when --timeout passes.

serve stops pi at --max-seconds, and aborts and stops it once the cost the
session reports passes --budget-usd.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from enum import IntEnum
from pathlib import Path
from typing import IO

DIALOGS = frozenset({"select", "confirm", "input", "editor"})
POLL_SECONDS = 0.05
KILL_GRACE_SECONDS = 10.0
TEXT_LIMIT, ARGS_LIMIT, RESULT_LIMIT = 4000, 400, 800


class Exit(IntEnum):
    SETTLED = 0
    REJECTED = 1
    DIALOG = 2
    GONE = 3
    TIMEOUT = 124


class Run:
    """The files one session is exchanged through."""

    def __init__(self, path: str) -> None:
        self.dir = Path(path)
        self.cmds = self.dir / "cmds.jsonl"
        self.events = self.dir / "events.jsonl"
        self.transcript = self.dir / "transcript.log"
        self.stderr = self.dir / "stderr.log"
        self.turn = self.dir / "turn.json"
        self.pid = self.dir / "serve.pid"
        self.exit_code = self.dir / "exit_code"

    def append_command(self, command: dict) -> None:
        # One write of one whole line, so lines from concurrent clients never interleave.
        with open(self.cmds, "ab") as f:
            f.write((json.dumps(command, ensure_ascii=False) + "\n").encode())

    def serving(self) -> bool:
        if self.exit_code.exists():
            return False
        try:
            os.kill(int(self.pid.read_text()), 0)
        except (OSError, ValueError):
            return False
        return True

    def events_size(self) -> int:
        try:
            return self.events.stat().st_size
        except FileNotFoundError:
            return 0


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# --- rendering ---------------------------------------------------------------


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}… [+{len(text) - limit} chars]"


def text_of(content: object) -> str:
    """The text in a message's or a tool result's content: a string, or a list of blocks."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, dict) and block.get("type") == "image":
            parts.append("[image]")
    return "".join(parts)


def describe(event: dict, streamed: bool) -> list[str]:
    """One-line renderings of an event. `streamed`: the assistant's text already went out as deltas."""
    kind = event.get("type")
    if kind == "message_end":
        message = event.get("message") or {}
        role, text = message.get("role"), text_of(message.get("content")).strip()
        lines = []
        if role == "assistant":
            if text and not streamed:
                lines.append(f"[assistant] {clip(text, TEXT_LIMIT)}")
            if message.get("stopReason") in ("error", "aborted"):
                lines.append(f"[assistant {message['stopReason']}] {message.get('errorMessage') or ''}".rstrip())
        elif role == "user" and streamed:
            lines.append(f"[user] {clip(text, TEXT_LIMIT)}")
        elif role == "custom" and message.get("display") and text:
            lines.append(f"[{message.get('customType')}] {clip(text, RESULT_LIMIT)}")
        return lines
    if kind == "tool_execution_start":
        args = json.dumps(event.get("args"), ensure_ascii=False)
        return [f"[tool] {event.get('toolName')} {clip(args, ARGS_LIMIT)}"]
    if kind == "tool_execution_end":
        result = event.get("result")
        text = text_of(result.get("content")) if isinstance(result, dict) else str(result or "")
        flag = " ERROR" if event.get("isError") else ""
        return [f"[result{flag}] {event.get('toolName')}: {clip(text.strip(), RESULT_LIMIT)}"]
    if kind == "extension_ui_request":
        return describe_ui(event)
    if kind == "extension_error":
        return [f"[extension error] {event.get('extensionPath')} ({event.get('event')}): {event.get('error')}"]
    if kind == "auto_retry_start":
        return [f"[retry] attempt {event.get('attempt')}/{event.get('maxAttempts')}: {event.get('errorMessage')}"]
    if kind == "auto_retry_end" and not event.get("success"):
        return [f"[retry] gave up: {event.get('finalError')}"]
    if kind == "compaction_end":
        outcome = "aborted" if event.get("aborted") else event.get("errorMessage") or "done"
        return [f"[compaction] {event.get('reason')}: {outcome}"]
    if kind == "response" and event.get("success") is False:
        return [f"[error] {event.get('command')}: {event.get('error')}"]
    if isinstance(kind, str) and kind.startswith("pidrive_"):
        return [f"[pidrive] {event.get('message')}"]
    return []


def describe_ui(event: dict) -> list[str]:
    method = event.get("method")
    if method == "notify":
        return [f"[notify {event.get('notifyType') or 'info'}] {event.get('message')}"]
    if method == "setStatus" and event.get("statusText"):
        return [f"[status] {event.get('statusKey')}: {event.get('statusText')}"]
    if method == "setWidget" and event.get("widgetLines"):
        return [f"[widget] {event.get('widgetKey')}: {clip(' | '.join(event['widgetLines']), RESULT_LIMIT)}"]
    if method in DIALOGS:
        lines = [f"[dialog] {method} {event.get('id')}: {event.get('title')}"]
        if event.get("message"):
            lines.append(f"  {event['message']}")
        if event.get("options"):
            lines.append("  options: " + " / ".join(map(str, event["options"])))
        if event.get("prefill"):
            lines.append(f"  prefill: {clip(event['prefill'], RESULT_LIMIT)}")
        if event.get("timeout"):
            lines.append(f"  resolves by itself after {event['timeout']} ms")
        return lines
    return []  # setTitle, set_editor_text, cleared statuses and widgets: nothing to read


class Transcript:
    """Renders events for someone following along with `tail -f`."""

    def __init__(self, stream: IO[str]) -> None:
        self.stream = stream
        self.open_line = False  # streamed text not yet ended with a newline
        self.pending_prefix = False  # an assistant message has started, but none of its text

    def write(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "message_start" and (event.get("message") or {}).get("role") == "assistant":
            self.pending_prefix = True
        elif kind == "message_update":
            delta = event.get("assistantMessageEvent") or {}
            if delta.get("type") == "text_delta":
                if self.pending_prefix:
                    self.end_line()
                    self.stream.write("[assistant] ")
                    self.pending_prefix = False
                self.stream.write(delta.get("delta", ""))
                self.open_line = True
        for line in describe(event, streamed=True):
            self.line(line)
        if kind == "message_end":
            self.end_line()
            self.pending_prefix = False
        elif kind == "agent_settled":
            self.line("── settled ──")
        self.stream.flush()

    def line(self, text: str) -> None:
        self.end_line()
        self.stream.write(text + "\n")

    def end_line(self) -> None:
        if self.open_line:
            self.stream.write("\n")
            self.open_line = False


# --- serve ---------------------------------------------------------------------


class Log:
    """events.jsonl and transcript.log. The stdout reader and serve itself both write here."""

    def __init__(self, run: Run) -> None:
        self.lock = threading.Lock()
        self.events = open(run.events, "ab")
        self.transcript = Transcript(open(run.transcript, "a", encoding="utf-8"))

    def record(self, line: bytes) -> dict | None:
        with self.lock:
            self.events.write(line + b"\n")
            self.events.flush()
            try:
                event = json.loads(line)
            except ValueError:
                event = None
            if isinstance(event, dict):
                self.transcript.write(event)
                return event
            self.transcript.line(f"[stdout] {line.decode(errors='replace')}")
            self.transcript.stream.flush()
            return None

    def note(self, kind: str, message: str, **fields: object) -> None:
        self.record(json.dumps({"type": f"pidrive_{kind}", "message": message, **fields}).encode())


class PiStdin:
    """pi's stdin, shared by the command feeder and the budget guard."""

    def __init__(self, stream: IO[bytes]) -> None:
        self.stream = stream
        self.lock = threading.Lock()
        self.closed = False

    def write(self, line: bytes) -> None:
        with self.lock:
            if self.closed:
                return
            try:
                self.stream.write(line)
                self.stream.flush()
            except (OSError, ValueError):  # pi has gone; its exit is reported elsewhere
                self.closed = True

    def close(self) -> None:
        with self.lock:
            if not self.closed:
                self.closed = True
                try:
                    self.stream.close()
                except OSError:
                    pass


def is_quit(line: bytes) -> bool:
    try:
        return json.loads(line).get("type") == "__quit"
    except (ValueError, AttributeError):
        return False


def feed(run: Run, stdin: PiStdin, done: threading.Event) -> None:
    """Forward each complete line appended to cmds.jsonl to pi's stdin."""
    with open(run.cmds, "rb") as commands:
        pending = b""
        while not done.is_set():
            chunk = commands.read()
            if not chunk:
                time.sleep(POLL_SECONDS)
                continue
            *lines, pending = (pending + chunk).split(b"\n")
            for line in lines:
                if not line.strip():
                    continue
                if is_quit(line):
                    stdin.close()  # pi shuts down on EOF (onInputEnd in rpc-mode.js)
                    return
                stdin.write(line + b"\n")


def cost_of(event: dict) -> float:
    """What one event adds to the session's spend: a message's usage, or a compaction's."""
    if event.get("type") == "message_end":
        usage = (event.get("message") or {}).get("usage")
    elif event.get("type") == "compaction_end":
        usage = (event.get("result") or {}).get("usage")
    else:
        return 0.0
    total = ((usage or {}).get("cost") or {}).get("total")
    return float(total) if isinstance(total, (int, float)) else 0.0


def read(stdout: IO[bytes], stdin: PiStdin, log: Log, budget: float) -> None:
    """Record pi's stdout. Once the session costs more than `budget`, abort the run and stop pi."""
    spent = 0.0
    for raw in stdout:  # bytes lines: split on b"\n" only, as RPC framing requires (U+2028 is not a break)
        line = raw[:-1] if raw.endswith(b"\n") else raw
        event = log.record(line[:-1] if line.endswith(b"\r") else line)
        if event is None or spent > budget:
            continue
        spent += cost_of(event)
        if spent > budget:
            log.note("budget", f"spent ${spent:.4f}, over the ${budget:.2f} budget: aborting and stopping pi",
                     spent=spent, budget=budget)
            stdin.write(b'{"type": "abort"}\n')
            closer = threading.Timer(2.0, stdin.close)  # EOF: pi shuts down once the abort is in
            closer.daemon = True
            closer.start()


def serve(args: argparse.Namespace) -> int:
    provider, model = os.environ.get("PI_PROVIDER"), os.environ.get("PI_MODEL")
    if not (provider and model):
        # No fallback spelled out here: the pin lives in pi-agent-experiments/shared/versions.env.
        print("pidrive serve: PI_PROVIDER and PI_MODEL are unset. Run it under "
              "pi-agent-experiments/shared/with-versions.sh, which exports the pinned pair.", file=sys.stderr)
        return 2
    run = Run(args.run)
    run.dir.mkdir(parents=True, exist_ok=True)
    if run.events_size() > 0:
        print(f"pidrive serve: {run.dir} already holds a session; use a fresh directory", file=sys.stderr)
        return 2
    run.cmds.touch()
    run.pid.write_text(f"{os.getpid()}\n")

    argv = [os.environ.get("PI_BIN", "pi"), "--mode", "rpc", "--provider", provider, "--model", model, *args.pi_args]
    with open(run.stderr, "ab") as stderr:
        proc = subprocess.Popen(argv, cwd=args.cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda *_: proc.terminate())

    log, stdin, done = Log(run), PiStdin(proc.stdin), threading.Event()
    reader = threading.Thread(target=read, args=(proc.stdout, stdin, log, args.budget_usd), daemon=True)
    reader.start()
    threading.Thread(target=feed, args=(run, stdin, done), daemon=True).start()
    print(f"pidrive: pi --model {provider}/{model} serving {run.dir} (pid {proc.pid})", flush=True)

    try:
        code = proc.wait(timeout=args.max_seconds)
    except subprocess.TimeoutExpired:
        log.note("timeout", f"--max-seconds {args.max_seconds:g} reached: stopping pi")
        proc.terminate()
        try:
            code = proc.wait(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait()
    # Drain what pi wrote before it went. Bounded, in case a child of pi still holds the pipe.
    reader.join(timeout=5)
    done.set()
    log.note("exit", f"pi exited with code {code}", code=code)
    run.exit_code.write_text(f"{code}\n")
    print(f"pidrive: pi exited with code {code}", flush=True)
    return code if code >= 0 else 128 - code


# --- clients -------------------------------------------------------------------


class Tail:
    """Records appended to a JSONL file after `offset`. A partial last line waits for its newline."""

    def __init__(self, path: Path, offset: int) -> None:
        self.path = path
        self.offset = offset

    def poll(self) -> list[tuple[int, dict]]:
        """New records, each with the offset just past it. Splits on b"\\n" only, like serve."""
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                data = f.read()
        except FileNotFoundError:
            return []
        records, start = [], 0
        while (newline := data.find(b"\n", start)) >= 0:
            line, start = data[start:newline], newline + 1
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append((self.offset + start, record))
        self.offset += start
        return records


def request(run: Run, command: dict, timeout: float) -> dict | None:
    """Send one command and return pi's response to it, or None if none came."""
    command = {"id": new_id("cmd"), **command}
    tail = Tail(run.events, run.events_size())
    run.append_command(command)
    deadline = time.monotonic() + timeout
    while True:
        alive = run.serving()  # checked before the read, so a response written just before exit is seen
        for _, event in tail.poll():
            if event.get("type") == "response" and event.get("id") == command["id"]:
                return event
        if not alive or time.monotonic() >= deadline:
            return None
        time.sleep(POLL_SECONDS)


def session_stats(run: Run) -> dict:
    response = request(run, {"type": "get_session_stats"}, timeout=10) if run.serving() else None
    return (response or {}).get("data") or {}


def stats_line(stats: dict) -> str:
    parts = []
    if isinstance(stats.get("cost"), (int, float)):
        parts.append(f"session ${stats['cost']:.4f}")
    if isinstance((stats.get("tokens") or {}).get("total"), int):
        parts.append(f"{stats['tokens']['total']:,} tokens")
    if isinstance(stats.get("toolCalls"), int):
        parts.append(f"{stats['toolCalls']} tool calls")
    percent = (stats.get("contextUsage") or {}).get("percent")
    if isinstance(percent, (int, float)):
        parts.append(f"context {percent:.0f}%")
    return " · ".join(parts) or "no stats"


@dataclass
class Turn:
    """What a client is waiting on. Saved between send, wait and ui."""

    offset: int
    prompt_id: str | None = None
    accepted: bool = True  # pi has answered the prompt command itself
    started: bool = False  # an agent run began after it

    def save(self, run: Run) -> None:
        run.turn.write_text(json.dumps(asdict(self)) + "\n")

    @classmethod
    def load(cls, run: Run) -> Turn:
        try:
            return cls(**json.loads(run.turn.read_text()))
        except (FileNotFoundError, ValueError, TypeError):
            return cls(offset=run.events_size())


def watch(run: Run, turn: Turn, timeout: float, grace: float) -> int:
    """Print the turn's events until pi is idle, a dialog opens, pi goes, or `timeout` passes."""
    tail = Tail(run.events, turn.offset)
    lines: list[str] = []
    quiet_from = time.monotonic()
    deadline = quiet_from + timeout
    probe: str | None = None

    def finish(code: Exit, offset: int, footer: str) -> int:
        turn.offset = offset
        turn.save(run)
        print("\n".join([*lines, f"── {footer} ──"]))
        return code

    while True:
        alive = run.serving()
        for offset, event in tail.poll():
            kind = event.get("type")
            if kind == "response" and event.get("id") == turn.prompt_id:
                if not event.get("success"):
                    lines.append(f"[rejected] {event.get('error')}")
                    return finish(Exit.REJECTED, offset, "prompt rejected")
                turn.accepted, quiet_from = True, time.monotonic()
                continue
            if kind == "response" and probe is not None and event.get("id") == probe:
                probe = None
                if not turn.started and not (event.get("data") or {}).get("isStreaming"):
                    return finish(Exit.SETTLED, offset, f"done, no agent run · {stats_line(session_stats(run))}")
                continue
            if kind == "agent_start":
                turn.started = True
            lines.extend(describe(event, streamed=False))
            if kind == "agent_settled":
                return finish(Exit.SETTLED, offset, f"settled · {stats_line(session_stats(run))}")
            if kind == "extension_ui_request" and event.get("method") in DIALOGS:
                how = "--value TEXT" if event.get("method") != "confirm" else "--confirm y|n"
                return finish(Exit.DIALOG, offset, f"dialog open: pidrive.py ui {run.dir} {event.get('id')} {how} (or --cancel)")
            if kind == "pidrive_exit":
                return finish(Exit.GONE, offset, "pi is not running")
        if not alive:
            return finish(Exit.GONE, tail.offset, "pi is not running")
        now = time.monotonic()
        if now >= deadline:
            return finish(Exit.TIMEOUT, tail.offset, f"still running after {timeout:g}s · {stats_line(session_stats(run))} · "
                          f"`pidrive.py wait {run.dir}`, or abort with "
                          f"`pidrive.py cmd {run.dir} '{{\"type\": \"abort\"}}'`")
        # pi answers a prompt just before its run starts, but answers an extension command only
        # once the handler has returned, and a run may never start. So when no run has started
        # `grace` seconds after the answer, ask pi whether anything is still streaming.
        if turn.accepted and not turn.started and probe is None and now - quiet_from >= grace:
            probe = new_id("probe")
            run.append_command({"id": probe, "type": "get_state"})
        time.sleep(POLL_SECONDS)


def require_serving(run: Run) -> bool:
    deadline = time.monotonic() + 10  # serve may have been started a moment ago
    while not run.pid.exists() and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
    if run.serving():
        return True
    print(f"pidrive: no pi is serving {run.dir}", file=sys.stderr)
    return False


def send(args: argparse.Namespace) -> int:
    run = Run(args.run)
    if not require_serving(run):
        return Exit.GONE
    command = {"id": new_id("prompt"), "type": "prompt", "message": args.message}
    if args.queue:
        command["streamingBehavior"] = args.queue
    turn = Turn(offset=run.events_size(), prompt_id=command["id"], accepted=False)
    run.append_command(command)
    return watch(run, turn, args.timeout, args.grace)


def wait(args: argparse.Namespace) -> int:
    run = Run(args.run)
    return watch(run, Turn.load(run), args.timeout, args.grace)


def ui(args: argparse.Namespace) -> int:
    run = Run(args.run)
    if not require_serving(run):
        return Exit.GONE
    response: dict = {"type": "extension_ui_response", "id": args.id}
    if args.cancel:
        response["cancelled"] = True
    elif args.confirm:
        response["confirmed"] = args.confirm == "y"
    else:
        response["value"] = args.value
    run.append_command(response)
    return watch(run, Turn.load(run), args.timeout, args.grace)


def cmd(args: argparse.Namespace) -> int:
    run = Run(args.run)
    if not require_serving(run):
        return Exit.GONE
    response = request(run, json.loads(args.json), args.timeout)
    if response is None:
        print(f"pidrive: no response within {args.timeout:g}s", file=sys.stderr)
        return Exit.TIMEOUT
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0 if response.get("success") else 1


def stop(args: argparse.Namespace) -> int:
    run = Run(args.run)
    if run.serving():
        stats = session_stats(run)
        print(f"final: {stats_line(stats)}")
        if stats.get("sessionFile"):
            print(f"session file: {stats['sessionFile']}")
        run.append_command({"type": "__quit"})
        deadline = time.monotonic() + args.timeout
        while not run.exit_code.exists() and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
    if not run.exit_code.exists():
        print(f"pidrive: pi did not exit within {args.timeout:g}s", file=sys.stderr)
        return 1
    code = run.exit_code.read_text().strip()
    print(f"pi exited with code {code}")
    return 0 if code == "0" else 1


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="pidrive.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run pi --mode rpc for RUN until stopped (start it in the background)",
                       usage="%(prog)s RUN [--cwd DIR] [--max-seconds S] [--budget-usd USD] [-- PI_ARGS...]")
    p.add_argument("run")
    p.add_argument("--cwd", default=".", help="pi's working directory")
    p.add_argument("--max-seconds", type=float, default=1800, help="stop pi after this long (default 1800)")
    p.add_argument("--budget-usd", type=float, default=0.50,
                   help="abort and stop pi once this process's session costs more (default 0.50)")
    p.set_defaults(func=serve)

    def turn_options(p: argparse.ArgumentParser) -> None:
        p.add_argument("--timeout", type=float, default=300, help="stop waiting after this long (default 300)")
        p.add_argument("--grace", type=float, default=1.0,
                       help="seconds without a run before asking pi whether it is idle (default 1)")

    p = sub.add_parser("send", help="send a prompt or slash command and wait for the turn")
    p.add_argument("run")
    p.add_argument("message")
    p.add_argument("--queue", choices=("steer", "followUp"), help="queue it while pi is still working")
    turn_options(p)
    p.set_defaults(func=send)

    p = sub.add_parser("wait", help="keep waiting on the turn")
    p.add_argument("run")
    turn_options(p)
    p.set_defaults(func=wait)

    p = sub.add_parser("ui", help="answer an extension dialog, then keep waiting on the turn")
    p.add_argument("run")
    p.add_argument("id")
    answer = p.add_mutually_exclusive_group(required=True)
    answer.add_argument("--value", help="the option or text (select, input, editor)")
    answer.add_argument("--confirm", choices=("y", "n"), help="the answer to a confirm")
    answer.add_argument("--cancel", action="store_true", help="dismiss the dialog")
    turn_options(p)
    p.set_defaults(func=ui)

    p = sub.add_parser("cmd", help="send any RPC command and print pi's response")
    p.add_argument("run")
    p.add_argument("json")
    p.add_argument("--timeout", type=float, default=120)
    p.set_defaults(func=cmd)

    p = sub.add_parser("stop", help="print the final stats and shut pi down")
    p.add_argument("run")
    p.add_argument("--timeout", type=float, default=30)
    p.set_defaults(func=stop)

    # Everything after serve's -- is pi's. Split it off here: argparse before 3.12 rejects
    # a -- that follows a subcommand's options, and Debian 12's python3 is 3.11.
    argv = list(sys.argv[1:] if argv is None else argv)
    pi_args: list[str] = []
    if argv[:1] == ["serve"] and "--" in argv:
        split = argv.index("--")
        argv, pi_args = argv[:split], argv[split + 1:]
    args = parser.parse_args(argv)
    args.pi_args = pi_args
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
