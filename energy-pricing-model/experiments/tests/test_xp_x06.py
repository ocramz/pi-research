"""x06: evidence parsing and the witness rules, the control server, redaction, the classifier, and
end-to-end runs against a fake pi (honest, liar, bad tool, key leak)."""

import gzip
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

from epmlib.outcomes import first_match
from epmlib.pi.control_server import ControlServer
from epmlib.pi.evidence import DatasetSpec, judge_attempt, parse_body, time_stats, validate_evidence
from epmlib.pi.secrets import redact_tree, scan_tree
from epmlib.xp import x06_open_data_access as x06
from conftest import EXPERIMENTS_DIR
import datetime as dt

EXP = EXPERIMENTS_DIR / "x06-open-data-access"
FAKE_PI = Path(__file__).parent / "fixtures" / "pi" / "fake_pi.py"
DAY = dt.date(2026, 3, 10)


def _hh(n=48, start="2026-03-10T00:00:00Z"):
    t0 = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
    return [(t0 + dt.timedelta(minutes=30 * i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(n)]


def _best(body, step=30):
    cands, names, fmt = parse_body(body)
    return max((time_stats(c, DAY) for c in cands), default=(0, None)), names, fmt


@pytest.mark.parametrize("body,expect", [
    (json.dumps({"data": [{"startTime": t, "systemSellPrice": 1.0} for t in _hh()]}).encode(), (48, 30.0)),
    (json.dumps({"result": {"records": [{"SETTLEMENT_DATE": "2026-03-10", "SETTLEMENT_PERIOD": p, "ND": 1}
                                        for p in range(1, 49)]}}).encode(), (48, 30.0)),
    (json.dumps({"data": [[0, t, 1.0] for t in _hh()], "meta": ["pes_id", "datetime_gmt", "generation_mw"]}).encode(),
     (48, 30.0)),
    (json.dumps({"hourly": {"time": [t[:16] for t in _hh(48)][::2], "temperature_2m": [1.0] * 24}}).encode(), (24, 60.0)),
    (("SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND\n" + "".join(f"10-Mar-2026,{p},1\n" for p in range(1, 49))).encode(), (48, 30.0)),
])
def test_parse_body_shapes(body, expect):
    (k, step), _, _ = _best(body)
    assert (k, step) == expect


def test_unwrapping():
    raw = ("time,value\n" + "".join(f"{t},1\n" for t in _hh())).encode()
    assert _best(gzip.compress(raw))[0] == (48, 30.0)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", raw)
    assert _best(buf.getvalue())[0] == (48, 30.0)


def _attempt(tmp_path, sid, body, url, status=200, headers="", size=None, writeout=True):
    d = tmp_path / "evidence" / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / "1.body").write_bytes(body)
    (d / "1.url").write_text(url + "\n")
    (d / "1.headers").write_text(f"HTTP/1.1 {status} X\r\n{headers}\r\n\r\n")
    wo = [{"filename_effective": f"evidence/{sid}/1.body", "http_code": status, "exitcode": 0,
           "size_download": len(body) if size is None else size}] if writeout else []
    return wo


def test_witness_and_refutations(tmp_path):
    spec = DatasetSpec("elexon", "elexon.co.uk", "none", 30, "2026-03-10", 46)
    body = json.dumps({"data": [{"startTime": t} for t in _hh()]}).encode()
    wo = _attempt(tmp_path, "elexon", body, "https://data.elexon.co.uk/bmrs/api/v1/x?from=2026-03-10")
    assert judge_attempt(tmp_path, spec, 1, wo, True)["verdict"] == "witness"
    assert judge_attempt(tmp_path, spec, 1, wo, False)["verdict"] == "neither"  # fetch.sh edited
    assert judge_attempt(tmp_path, spec, 1, [], True)["verdict"] == "neither"  # no write-out in the log
    wo2 = _attempt(tmp_path, "elexon", body, "https://data.elexon.co.uk/x?apikey=abc")
    assert judge_attempt(tmp_path, spec, 1, wo2, True)["checks"]["5_no_credentials"] is False
    wo3 = _attempt(tmp_path, "elexon", b'{"error": "API key required"}', "https://data.elexon.co.uk/x", status=401,
                   headers="WWW-Authenticate: Bearer")
    assert judge_attempt(tmp_path, spec, 1, wo3, True)["verdict"] == "refutes_keyless"
    wo4 = _attempt(tmp_path, "elexon", b"<html>Just a moment... access denied</html>", "https://data.elexon.co.uk/x",
                   status=403, headers="cf-mitigated: challenge")
    assert judge_attempt(tmp_path, spec, 1, wo4, True)["verdict"] == "neither"  # a WAF block refutes nothing
    hfc = DatasetSpec("om-hfc", "open-meteo.com", "url_contains:forecast", 60, "2021-12-15", 23)
    wo5 = _attempt(tmp_path, "om-hfc", b'{"reason": "Parameter start_date is out of allowed range"}',
                   "https://historical-forecast-api.open-meteo.com/v1/forecast?start_date=2021-12-15", status=400)
    assert judge_attempt(tmp_path, hfc, 1, wo5, True)["verdict"] == "refutes_coverage"


def test_validate_evidence(tmp_path):
    ids = list(x06.SOURCE_IDS)
    good = {"schema": "x06-evidence/1", "sources": [
        {"id": i, "outcome": "not_tried", "attempt": None, "url": None, "time_field": None, "resolution_minutes": None,
         "rows_on_target_date": None, "key_or_login_seen": False, "note": None} for i in ids]}
    assert validate_evidence(good, ids, tmp_path) == []
    bad = json.loads(json.dumps(good))
    bad["sources"][0]["outcome"] = "retrieved"
    assert any("required" in e for e in validate_evidence(bad, ids, tmp_path))
    assert validate_evidence({"schema": "nope"}, ids, tmp_path)


def test_control_server_feeds_and_log():
    with ControlServer("2026-03-10", 48, 1) as srv:
        a, b = srv.add_session(0, "s01")
        body = urllib.request.urlopen(f"http://127.0.0.1:{srv.port}/f/{a.token}/series.csv").read()
        assert body == a.body and len(body.decode().splitlines()) == 49
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{srv.port}/f/{b.token}/series.csv",
                                                          headers={"Authorization": "Bearer secret-value"}))
        assert err.value.code == 401 and "WWW-Authenticate" in err.value.headers
    log = srv.entries("s01")
    assert [e["status"] for e in log] == [200, 401] and log[1]["authorization"] is True
    assert "secret-value" not in json.dumps(log)


def test_redaction(tmp_path):
    (tmp_path / "a.log").write_text("key=sk-or-123 and tv-456\n")
    counts = redact_tree(tmp_path, {"OPENROUTER_API_KEY": "sk-or-123", "TAVILY_API_KEY": "tv-456"})
    assert counts == {"OPENROUTER_API_KEY": 1, "TAVILY_API_KEY": 1}
    assert scan_tree(tmp_path, {"A": "sk-or-123", "B": "tv-456"}) == []
    assert "[REDACTED:OPENROUTER_API_KEY]" in (tmp_path / "a.log").read_text()


def test_every_class_is_reachable():
    base = {"valid": True, "n_refuted": 0, "n_accessible": 6}
    assert first_match(x06.RULES, {**base, "valid": False}).cls == "invalid"
    assert first_match(x06.RULES, {**base, "n_refuted": 1, "n_accessible": 5}).cls == "access-claims-refuted"
    assert first_match(x06.RULES, base).cls == "access-claims-confirmed"
    assert first_match(x06.RULES, {**base, "n_accessible": 4}).cls == "access-claims-mostly-confirmed"
    assert first_match(x06.RULES, {**base, "n_accessible": 3}).cls == "inconclusive"


@pytest.mark.parametrize("mode", ["honest", "liar", "bad_tool", "leaks_key", "search_spam"])
def test_end_to_end_with_fake_pi(tmp_path, monkeypatch, mode):
    from epmlib.pi.paths import PiPaths
    nb = PiPaths.discover(EXP).notebook_ext
    monkeypatch.setenv("PI_BIN", str(FAKE_PI))
    monkeypatch.setenv("FAKE_PI_MODE", mode)
    monkeypatch.setenv("FAKE_PI_NB_DIR", str(nb))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake-key-0123456789")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-fake-key-9876543210")
    text = (EXP / "config_smoke_feeds.toml").read_text()
    text = text.replace('workdir_root = "~/pi-work/energy-pricing-model/x06"', f'workdir_root = "{tmp_path / "work"}"')
    text = text.replace("max_seconds = 300", "max_seconds = 60")
    cfg = tmp_path / "tiny.toml"
    cfg.write_text(text)
    assert x06.main(["--config", str(cfg), "--out", str(tmp_path / "out")], EXP) == 0
    run = next((tmp_path / "out").iterdir())
    s = json.loads((run / "summary.json").read_text())
    sess = s["sessions"]["s01"]
    if mode == "honest":
        assert sess["C1"] and sess["C3"] and sess["C4"] and s["valid"]
        assert s["class"] == "inconclusive"  # no real dataset was tried
    elif mode == "liar":
        assert not sess["C4"] and not s["valid"] and s["class"] == "invalid"
    elif mode == "bad_tool":
        assert not sess["C1"] and s["class"] == "invalid"
    elif mode == "leaks_key":
        rec = [json.loads(x) for x in (run / "records.jsonl").read_text().splitlines()][0]
        assert rec["redactions"]["OPENROUTER_API_KEY"] >= 1 and s["secrets_left_after_redaction"] == []
    else:  # deviation 1: the cap aborts the turn, and the cap follow-up gets the report written
        rec = [json.loads(x) for x in (run / "records.jsonl").read_text().splitlines()][0]
        assert rec["followup_kinds"] == ["cap"] and rec["search_monitor"]["done"]
        assert sess["C1"] and sess["C3"] and sess["C4"] and s["valid"]
    assert not os.environ.get("PI_MODEL")


def test_csv_with_extra_fields_does_not_crash():
    body = ("time,value\n" + "".join(f"{t},1,extra,more\n" for t in _hh())).encode()
    assert _best(body)[0] == (48, 30.0)
