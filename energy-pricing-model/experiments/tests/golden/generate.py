"""Regenerate the golden fixtures. Refuses to overwrite an existing file without --force: a changed
fixture means results that earlier runs depend on have moved.

    uv run python tests/golden/generate.py [--force]"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_pricing import GOLDEN as PRICING_GOLDEN, golden_stats as pricing_stats  # noqa: E402
from test_toy import GOLDEN, _golden_stats  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    fixtures = {GOLDEN: _golden_stats, PRICING_GOLDEN: pricing_stats}
    for path, make in fixtures.items():
        if path.exists() and not args.force:
            print(f"{path} exists; skipped (pass --force to overwrite)", file=sys.stderr)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(make(), indent=2, sort_keys=True) + "\n")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
