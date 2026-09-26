"""Redaction. The agent's bash inherits both API keys, so any committed log could contain them. Values
are replaced byte for byte with `[REDACTED:<NAME>]`; only counts are ever reported."""

from __future__ import annotations

from pathlib import Path


def redact_tree(root: Path, secrets: dict[str, str]) -> dict[str, int]:
    counts = {name: 0 for name in secrets}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        changed = data
        for name, value in secrets.items():
            if value:
                needle = value.encode()
                n = changed.count(needle)
                if n:
                    counts[name] += n
                    changed = changed.replace(needle, f"[REDACTED:{name}]".encode())
        if changed is not data:
            path.write_bytes(changed)
    return counts


def scan_tree(root: Path, secrets: dict[str, str]) -> list[str]:
    """Files that still contain a secret (reads gzip members too)."""
    import gzip
    hits = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        if path.suffix == ".gz":
            try:
                data = gzip.decompress(data)
            except OSError:
                pass
        if any(v and v.encode() in data for v in secrets.values()):
            hits.append(str(path.relative_to(root)))
    return hits
