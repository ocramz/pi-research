"""The local control feeds of x06, on 127.0.0.1 with a random port.

feed-a (token A) answers 200 with a CSV `time,value` of 48 half-hours on the target date; its sha256
is kept. feed-b (token B) answers 401 with `WWW-Authenticate` and `{"error": "API key required"}`.
The access log keeps statuses and header *names*, never values."""

from __future__ import annotations

import datetime as dt
import hashlib
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..rng import generator


@dataclass
class Feed:
    session: str
    kind: str  # "a" or "b"
    token: str
    body: bytes = b""
    sha256: str = ""


@dataclass
class ControlServer:
    feed_date: str
    rows: int
    seed: int
    log: list[dict] = field(default_factory=list)
    _feeds: dict[str, Feed] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parts = self.path.split("?")[0].strip("/").split("/")
                feed = server._feeds.get(parts[1]) if len(parts) == 3 and parts[0] == "f" else None
                if feed is None:
                    status, body, headers = 404, b"not found\n", {"Content-Type": "text/plain"}
                elif feed.kind == "a":
                    status, body, headers = 200, feed.body, {"Content-Type": "text/csv"}
                else:
                    status, body = 401, b'{"error": "API key required"}\n'
                    headers = {"Content-Type": "application/json", "WWW-Authenticate": 'Bearer realm="feed-b"'}
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                with server._lock:
                    server.log.append({"time": time.time(), "path": self.path.split("?")[0], "status": status,
                                       "session": feed.session if feed else None,
                                       "feed": feed.kind if feed else None,
                                       "authorization": "authorization" in {h.lower() for h in self.headers},
                                       "header_names": sorted(self.headers.keys())})

            def log_message(self, *args: object) -> None:  # silence stderr
                return

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> ControlServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def add_session(self, index: int, name: str) -> tuple[Feed, Feed]:
        rng = generator(self.seed, 602, index)
        token_a, token_b = rng.bytes(8).hex(), rng.bytes(8).hex()
        start = dt.datetime.fromisoformat(self.feed_date).replace(tzinfo=dt.UTC)
        values = generator(self.seed, 601, index).uniform(0.0, 100.0, self.rows)
        lines = ["time,value"] + [f"{(start + dt.timedelta(minutes=30 * i)).strftime('%Y-%m-%dT%H:%M:%SZ')},{v:.4f}"
                                  for i, v in enumerate(values)]
        body = ("\n".join(lines) + "\n").encode()
        a = Feed(name, "a", token_a, body, hashlib.sha256(body).hexdigest())
        b = Feed(name, "b", token_b)
        with self._lock:
            self._feeds[token_a] = a
            self._feeds[token_b] = b
        return a, b

    def entries(self, session: str) -> list[dict]:
        with self._lock:
            return [e for e in self.log if e["session"] == session]
