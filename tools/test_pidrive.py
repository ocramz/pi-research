"""Offline tests for pidrive.py, against a fake pi that speaks just enough of the RPC protocol.

Nothing here reaches a model or the network. Run from the repo root with

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PIDRIVE = Path(__file__).resolve().parent / "pidrive.py"

# Answers the commands pidrive sends and streams the events pi would. Like pi, it
# answers an extension command only after the command has run, and exits on EOF.
FAKE_PI = r'''#!/usr/bin/env python3
import json, os, sys

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
with open(os.environ["FAKE_PI_ARGV"], "w") as f:
    json.dump(sys.argv[1:], f)

def out(event):
    # ensure_ascii=False puts a raw U+2028 on the wire, as Node's JSON.stringify does.
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def respond(command, success=True, **fields):
    out({"type": "response", "id": command.get("id"), "command": command["type"], "success": success, **fields})

def say(text, cost):
    out({"type": "message_start", "message": {"role": "assistant", "content": []}})
    out({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": text}})
    out({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": text}],
                                            "stopReason": "stop", "usage": {"cost": {"total": cost}}}})

def settle():
    global streaming
    streaming = False
    out({"type": "agent_end", "messages": []})
    out({"type": "agent_settled"})

spent, streaming, dialog = 0.0, False, None
for line in sys.stdin:
    command = json.loads(line)
    kind = command["type"]
    if kind == "get_state":
        respond(command, data={"isStreaming": streaming, "model": {"provider": "fake", "id": "fake-model"}})
    elif kind == "get_session_stats":
        respond(command, data={"sessionFile": "/fake/session.jsonl", "cost": spent, "tokens": {"total": 42},
                               "toolCalls": 1, "contextUsage": {"percent": 3}})
    elif kind == "abort":
        respond(command)
        if streaming:
            settle()
    elif kind == "extension_ui_response" and command["id"] == dialog:
        dialog = None
        say(f"picked {command.get('value')}", 0.001)
        spent += 0.001
        settle()
    elif kind == "prompt":
        message = command["message"]
        if message == "reject":
            respond(command, success=False, error="No API key found for fake")
            continue
        if message == "/board":
            out({"type": "extension_ui_request", "id": "n-1", "method": "notify", "message": "3 stories, 2 open"})
            respond(command)
            continue
        respond(command)
        streaming = True
        out({"type": "agent_start"})
        if message == "hello":
            out({"type": "tool_execution_start", "toolCallId": "t-1", "toolName": "bash", "args": {"command": "ls"}})
            out({"type": "tool_execution_end", "toolCallId": "t-1", "toolName": "bash",
                 "result": {"content": [{"type": "text", "text": "a.txt"}]}, "isError": False})
            say("Hi there friend", 0.001)
            spent += 0.001
            settle()
        elif message == "dialog":
            dialog = "dlg-1"
            out({"type": "extension_ui_request", "id": dialog, "method": "select", "title": "Pick one",
                 "options": ["A", "B"]})
        elif message == "expensive":
            say("that was costly", 1.0)
            spent += 1.0
        # "expensive" and "hang" keep working until aborted.
'''


class PidriveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pidrive-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        fake = self.tmp / "fake-pi"
        fake.write_text(FAKE_PI)
        fake.chmod(0o755)
        self.run_dir = self.tmp / "run"
        self.env = {
            **os.environ,
            "PI_BIN": str(fake),
            "PI_PROVIDER": "fake",
            "PI_MODEL": "fake-model",
            "FAKE_PI_ARGV": str(self.tmp / "argv.json"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }

    def serve(self, *options: str) -> subprocess.Popen:
        server = subprocess.Popen(
            [sys.executable, str(PIDRIVE), "serve", str(self.run_dir), "--cwd", str(self.tmp), *options],
            env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self.reap, server)
        return server

    @staticmethod
    def reap(server: subprocess.Popen) -> None:
        # Killing serve closes the fake's stdin, and the fake exits on EOF like pi.
        if server.poll() is None:
            server.kill()
        server.wait(timeout=10)

    def pidrive(self, command: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(PIDRIVE), command, str(self.run_dir), *args],
            env=env or self.env, capture_output=True, encoding="utf-8", timeout=60,
        )

    def test_send_summarises_the_turn(self) -> None:
        self.serve()
        result = self.pidrive("send", "hello")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('[tool] bash {"command": "ls"}', result.stdout)
        self.assertIn("[result] bash: a.txt", result.stdout)
        self.assertIn("[assistant] Hi there friend", result.stdout)
        self.assertIn("settled · session $0.0010 · 42 tokens · 1 tool calls · context 3%", result.stdout)
        transcript = (self.run_dir / "transcript.log").read_text(encoding="utf-8")
        self.assertIn("[assistant] Hi there friend", transcript)
        self.assertIn("── settled ──", transcript)

    def test_u2028_inside_a_record_is_not_a_line_break(self) -> None:
        self.serve()
        self.pidrive("send", "hello")
        raw = (self.run_dir / "events.jsonl").read_bytes()
        self.assertIn(" ".encode(), raw)  # it reached the log unescaped...
        events = [json.loads(line) for line in raw.split(b"\n") if line]
        deltas = [e["assistantMessageEvent"]["delta"] for e in events if e["type"] == "message_update"]
        self.assertEqual(deltas, ["Hi there friend"])  # ...and stayed inside one record

    def test_serve_passes_the_pins_and_extra_arguments_to_pi(self) -> None:
        self.serve("--", "--session-dir", "somewhere")
        self.pidrive("send", "hello")  # once pi has answered, it has written its argv
        argv = json.loads((self.tmp / "argv.json").read_text())
        self.assertEqual(
            argv, ["--mode", "rpc", "--provider", "fake", "--model", "fake-model", "--session-dir", "somewhere"]
        )

    def test_serve_refuses_without_a_model_pin(self) -> None:
        env = {k: v for k, v in self.env.items() if k != "PI_MODEL"}
        result = self.pidrive("serve", env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("with-versions.sh", result.stderr)

    def test_serve_refuses_a_used_run_directory(self) -> None:
        self.serve()
        self.pidrive("send", "hello")
        self.pidrive("stop")
        again = self.pidrive("serve")
        self.assertEqual(again.returncode, 2)
        self.assertIn("already holds a session", again.stderr)

    def test_rejected_prompt(self) -> None:
        self.serve()
        result = self.pidrive("send", "reject")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[rejected] No API key found for fake", result.stdout)

    def test_dialog_is_surfaced_then_answered(self) -> None:
        self.serve()
        opened = self.pidrive("send", "dialog")
        self.assertEqual(opened.returncode, 2, opened.stdout + opened.stderr)
        self.assertIn("[dialog] select dlg-1: Pick one", opened.stdout)
        self.assertIn("options: A / B", opened.stdout)
        answered = self.pidrive("ui", "dlg-1", "--value", "B")
        self.assertEqual(answered.returncode, 0, answered.stdout + answered.stderr)
        self.assertIn("[assistant] picked B", answered.stdout)

    def test_extension_command_that_starts_no_run(self) -> None:
        self.serve()
        result = self.pidrive("send", "/board", "--grace", "0.2", "--timeout", "10")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[notify info] 3 stories, 2 open", result.stdout)
        self.assertIn("done, no agent run", result.stdout)

    def test_timeout_then_abort_then_wait(self) -> None:
        self.serve()
        running = self.pidrive("send", "hang", "--timeout", "1")
        self.assertEqual(running.returncode, 124, running.stdout + running.stderr)
        self.assertIn("still running after 1s", running.stdout)
        aborted = self.pidrive("cmd", '{"type": "abort"}')
        self.assertEqual(aborted.returncode, 0, aborted.stdout + aborted.stderr)
        self.assertEqual(json.loads(aborted.stdout)["command"], "abort")
        settled = self.pidrive("wait", "--timeout", "10")
        self.assertEqual(settled.returncode, 0, settled.stdout + settled.stderr)
        self.assertIn("── settled", settled.stdout)

    def test_budget_aborts_the_run_and_stops_pi(self) -> None:
        server = self.serve("--budget-usd", "0.5")
        result = self.pidrive("send", "expensive")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[pidrive] spent $1.0000, over the $0.50 budget", result.stdout)
        self.assertEqual(server.wait(timeout=20), 0)
        self.assertEqual((self.run_dir / "exit_code").read_text().strip(), "0")

    def test_max_seconds_stops_pi(self) -> None:
        server = self.serve("--max-seconds", "1")
        result = self.pidrive("send", "hang", "--timeout", "30")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("[pidrive] --max-seconds 1 reached", result.stdout)
        self.assertNotEqual(server.wait(timeout=20), 0)

    def test_stop_shuts_pi_down(self) -> None:
        server = self.serve()
        self.pidrive("send", "hello")
        result = self.pidrive("stop")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("session file: /fake/session.jsonl", result.stdout)
        self.assertIn("pi exited with code 0", result.stdout)
        self.assertEqual(server.wait(timeout=20), 0)
        self.assertEqual(self.pidrive("send", "hello").returncode, 3)


if __name__ == "__main__":
    unittest.main()
