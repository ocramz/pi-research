"""x06 evidence: the agent's `evidence.json` (schema x06-evidence/1), parsing of saved bodies, and
the registered witness and refutation rules (PREREG, Definitions). Verdicts use only saved files."""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

SCHEMA = "x06-evidence/1"
OUTCOMES = ("retrieved", "key_required", "not_found", "failed", "not_tried")
CRED_PARAM = re.compile(r"(?i)key|token|auth|password|secret|signature")
KEY_BODY = re.compile(r"(?i)api[ _-]?key|subscription[ _-]?key|access[ _-]?token|unauthori[sz]ed|log ?in|sign ?in|regist")
WAF_BODY = re.compile(r"(?i)captcha|just a moment|attention required|access denied")
COVERAGE_BODY = re.compile(r"(?i)(out of|outside).{0,40}(range|allowed)|not available|no data")
DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y")


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    host_suffix: str
    identity: str
    step_minutes: int
    target_date: str
    min_distinct_times: int


# --- evidence.json ------------------------------------------------------------------------------------------


def validate_evidence(obj: Any, ids: list[str], workdir: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        return [f"schema must be {SCHEMA!r}"]
    sources = obj.get("sources")
    if not isinstance(sources, list):
        return ["sources must be a list"]
    seen = [s.get("id") for s in sources if isinstance(s, dict)]
    for i in ids:
        if seen.count(i) != 1:
            errors.append(f"id {i!r} must appear exactly once")
    for s in sources:
        if not isinstance(s, dict):
            errors.append("each source must be an object")
            continue
        sid = s.get("id")
        if sid not in ids:
            errors.append(f"unknown id {sid!r}")
        if s.get("outcome") not in OUTCOMES:
            errors.append(f"{sid}: outcome must be one of {list(OUTCOMES)}")
        att = s.get("attempt")
        if att is not None and not (isinstance(att, int) and 1 <= att <= 6):
            errors.append(f"{sid}: attempt must be an integer 1-6 or null")
        for k in ("url", "time_field", "note"):
            if s.get(k) is not None and not isinstance(s.get(k), str):
                errors.append(f"{sid}: {k} must be a string or null")
        if s.get("resolution_minutes") not in (30, 60, None):
            errors.append(f"{sid}: resolution_minutes must be 30, 60 or null")
        if s.get("rows_on_target_date") is not None and not isinstance(s.get("rows_on_target_date"), int):
            errors.append(f"{sid}: rows_on_target_date must be an integer or null")
        if not isinstance(s.get("key_or_login_seen"), bool):
            errors.append(f"{sid}: key_or_login_seen must be true or false")
        if s.get("outcome") == "retrieved":
            for k in ("attempt", "url", "time_field", "resolution_minutes", "rows_on_target_date"):
                if s.get(k) is None:
                    errors.append(f"{sid}: {k} is required when outcome is retrieved")
            if isinstance(att, int) and not (workdir / "evidence" / str(sid) / f"{att}.body").exists():
                errors.append(f"{sid}: evidence/{sid}/{att}.body does not exist")
    return errors


def agent_outcomes(obj: Any) -> dict[str, str]:
    if not isinstance(obj, dict) or not isinstance(obj.get("sources"), list):
        return {}
    return {s["id"]: s.get("outcome") for s in obj["sources"] if isinstance(s, dict) and "id" in s}


# --- bodies ----------------------------------------------------------------------------------------------------


def unwrap(body: bytes) -> bytes:
    if body[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(body)
        except OSError:
            return body
    if body[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                return z.read(names[0]) if names else body
        except zipfile.BadZipFile:
            return body
    return body


def parse_dt(v: Any) -> dt.datetime | None:
    if not isinstance(v, str):
        return None
    s = v.strip()
    if len(s) < 10 or not s[:4].isdigit() and not s[:2].isdigit():
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(s) <= 10:  # a bare date is not a time
        return None
    return t.replace(tzinfo=dt.UTC) if t.tzinfo is None else t.astimezone(dt.UTC)


def parse_date(v: Any) -> dt.date | None:
    if not isinstance(v, str):
        return None
    s = v.strip()[:11]
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _period(v: Any) -> int | None:
    try:
        p = int(float(v))
    except (TypeError, ValueError):
        return None
    return p if 1 <= p <= 50 else None


@dataclass
class Candidate:
    field: str
    times: list[dt.datetime]


def _from_records(rows: list[dict[str, Any]]) -> list[Candidate]:
    keys = sorted({k for r in rows for k in r if isinstance(k, str)})
    out = []
    for k in keys:
        ts = [parse_dt(r.get(k)) for r in rows]
        good = [t for t in ts if t is not None]
        if good and len(good) >= 0.5 * len(rows):
            out.append(Candidate(k, good))
    date_keys = [k for k in keys if re.search(r"(?i)date", k) and not re.search(r"(?i)time", k)]
    period_keys = [k for k in keys if re.search(r"(?i)period", k)]
    for dk in date_keys:
        for pk in period_keys:
            ts = []
            for r in rows:
                d, p = parse_date(r.get(dk)), _period(r.get(pk))
                if d is not None and p is not None:
                    ts.append(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC) + dt.timedelta(minutes=30 * (p - 1)))
            if ts and len(ts) >= 0.5 * len(rows):
                out.append(Candidate(f"{dk}+{pk}", ts))
    return out


def _walk_json(obj: Any, names: set[str], depth: int = 0) -> list[Candidate]:
    if depth > 6:
        return []
    out: list[Candidate] = []
    if isinstance(obj, dict):
        names.update(str(k) for k in obj)
        cols = next((obj[k] for k in ("meta", "columns", "fields") if isinstance(obj.get(k), list)
                     and all(isinstance(c, str) for c in obj[k])), None)
        for k, v in obj.items():
            if isinstance(v, list) and v and all(isinstance(x, str) for x in v[:50]):
                ts = [parse_dt(x) for x in v]
                good = [t for t in ts if t is not None]
                if good and len(good) >= 0.5 * len(v):
                    out.append(Candidate(str(k), good))
            if cols and isinstance(v, list) and v and all(isinstance(r, list) and len(r) == len(cols) for r in v[:50]):
                names.update(cols)
                out += _from_records([dict(zip(cols, r)) for r in v])
            out += _walk_json(v, names, depth + 1)
    elif isinstance(obj, list) and obj:
        if all(isinstance(r, dict) for r in obj[:50]):
            dicts = [r for r in obj if isinstance(r, dict)]
            for r in dicts[:5]:
                names.update(str(k) for k in r)
            out += _from_records(dicts)
        for x in obj[:5]:
            if isinstance(x, (dict, list)):
                out += _walk_json(x, names, depth + 1)
    return out


def parse_body(body: bytes) -> tuple[list[Candidate], set[str], str]:
    """(candidate time series, field names seen, format)."""
    raw = unwrap(body)
    text = raw.decode("utf-8", errors="replace")
    names: set[str] = set()
    stripped = text.lstrip()
    if stripped[:1] in "{[":
        try:
            obj = json.loads(text)
            return _walk_json(obj, names), names, "json"
        except ValueError:
            pass
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    # Fields beyond the header land under the key None: ignore them (deviation 1's parser fix).
    rows = [{k: v for k, v in r.items() if k is not None}
            for r in csv.DictReader(io.StringIO(text), dialect=dialect)]
    if rows and rows[0]:
        names.update(k for k in rows[0] if k)
        return _from_records(rows), names, "csv"
    return [], names, "unknown"


def time_stats(c: Candidate, target: dt.date) -> tuple[int, float | None]:
    """(distinct times on the target date, modal step in minutes between them)."""
    on = sorted({t for t in c.times if t.date() == target})
    if len(on) < 2:
        return len(on), None
    diffs = [(b - a).total_seconds() / 60 for a, b in zip(on, on[1:])]
    return len(on), Counter(diffs).most_common(1)[0][0]


def identity_ok(rule: str, url: str, names: set[str]) -> bool:
    u = url.lower()
    if rule == "none":
        return True
    kind, _, word = rule.partition(":")
    if kind == "url_or_field_contains":
        return word in u or any(word in n.lower() for n in names)
    if kind == "url_excludes":
        return word not in u
    if kind == "url_contains":
        return word in u
    raise ValueError(f"unknown identity rule {rule!r}")


def last_headers(path: Path) -> tuple[int | None, dict[str, str]]:
    if not path.exists():
        return None, {}
    blocks = [b for b in re.split(r"\r?\n\r?\n", path.read_text(errors="replace")) if b.strip().startswith("HTTP")]
    if not blocks:
        return None, {}
    lines = blocks[-1].splitlines()
    m = re.match(r"HTTP/\S+\s+(\d{3})", lines[0])
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return (int(m.group(1)) if m else None), headers


# --- the registered rules ----------------------------------------------------------------------------------


def judge_attempt(workdir: Path, spec: DatasetSpec, n: int, writeouts: list[dict], fetch_ok: bool) -> dict[str, Any]:
    d = workdir / "evidence" / spec.id
    body_path, url_path = d / f"{n}.body", d / f"{n}.url"
    url = url_path.read_text().strip() if url_path.exists() else ""
    body = body_path.read_bytes() if body_path.exists() else b""
    wo = [w for w in writeouts if w.get("filename_effective") == f"evidence/{spec.id}/{n}.body"]
    w = wo[-1] if wo else {}
    status_h, headers = last_headers(d / f"{n}.headers")
    status = w.get("http_code") if wo else status_h
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    checks = {
        "1_writeout": bool(wo),
        "2_fetch_sh_unchanged": fetch_ok,
        "3_http_200": wo != [] and w.get("http_code") == 200 and w.get("exitcode") == 0,
        "4_host": host == spec.host_suffix or host.endswith("." + spec.host_suffix),
        "5_no_credentials": not parts.username and not parts.password
                            and not any(CRED_PARAM.search(k) for k, _ in parse_qsl(parts.query, keep_blank_values=True)),
        "6_size": body_path.exists() and wo != [] and body_path.stat().st_size == w.get("size_download"),
    }
    candidates, names, fmt = parse_body(body) if body else ([], set(), "empty")
    target = dt.date.fromisoformat(spec.target_date)
    best = {"field": None, "distinct": 0, "step": None}
    ok7 = False
    for c in candidates:
        k, step = time_stats(c, target)
        if k > best["distinct"]:
            best = {"field": c.field, "distinct": k, "step": step}
        if k >= spec.min_distinct_times and step == spec.step_minutes:
            ok7 = True
            best = {"field": c.field, "distinct": k, "step": step}
            break
    checks["7_times"] = ok7
    checks["8_identity"] = identity_ok(spec.identity, url, names)
    witness = all(checks.values())
    text = body[:200_000].decode("utf-8", errors="replace")
    waf = "cf-mitigated" in headers or bool(WAF_BODY.search(text))
    refutes_keyless = (checks["1_writeout"] and checks["2_fetch_sh_unchanged"] and checks["4_host"]
                       and checks["5_no_credentials"] and status in (401, 403)
                       and ("www-authenticate" in headers or bool(KEY_BODY.search(text))) and not waf)
    refutes_coverage = (spec.id == "om-hfc" and body_path.exists() and status in (400, 404, 422)
                        and "2021-12-15" in url and bool(COVERAGE_BODY.search(text)))
    verdict = "witness" if witness else "refutes_keyless" if refutes_keyless else \
        "refutes_coverage" if refutes_coverage else "neither"
    return {"n": n, "url": url, "http_code": status, "format": fmt, "best_series": best, "checks": checks,
            "waf": waf, "verdict": verdict, "body_sha256": _sha(body) if body else None}


def _sha(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()


def judge_dataset(workdir: Path, spec: DatasetSpec, writeouts: list[dict], fetch_ok: bool) -> dict[str, Any]:
    d = workdir / "evidence" / spec.id
    ns = sorted(int(p.stem) for p in d.glob("*.body") if p.stem.isdigit()) if d.exists() else []
    attempts = [judge_attempt(workdir, spec, n, writeouts, fetch_ok) for n in ns]
    return {"attempts": attempts,
            "witness": any(a["verdict"] == "witness" for a in attempts),
            "refuted": any(a["verdict"] in ("refutes_keyless", "refutes_coverage") for a in attempts)}
