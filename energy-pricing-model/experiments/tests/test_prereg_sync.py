"""What a PREREG registers verbatim must equal what the code uses: config.toml, the x06 prompt,
follow-up and fetch.sh, and the order of the outcome classes."""

import importlib
import tomllib

import pytest

from epmlib.registered import outcome_classes, registered_blocks
from conftest import EXPERIMENTS_DIR

EXPERIMENTS = sorted(p for p in EXPERIMENTS_DIR.glob("x[0-9][0-9]-*") if (p / "PREREG.md").exists())


def test_all_six_are_registered():
    assert [p.name[:3] for p in EXPERIMENTS] == ["x01", "x02", "x03", "x04", "x05", "x06"]


@pytest.mark.parametrize("exp", EXPERIMENTS, ids=lambda p: p.name)
def test_registered_config_parses_and_names_the_experiment(exp):
    blocks = registered_blocks((exp / "PREREG.md").read_text(encoding="utf-8"))
    kind, content = blocks["config.toml"]
    assert kind == "config"
    assert tomllib.loads(content)["experiment"]["name"] == exp.name


@pytest.mark.parametrize("exp", EXPERIMENTS, ids=lambda p: p.name)
def test_registered_files_equal_the_working_files(exp):
    blocks = registered_blocks((exp / "PREREG.md").read_text(encoding="utf-8"))
    for name, (kind, content) in blocks.items():
        path = exp / name
        if not path.exists():
            continue  # not implemented yet
        if kind == "config":
            assert tomllib.loads(path.read_text(encoding="utf-8")) == tomllib.loads(content), name
        else:
            assert path.read_text(encoding="utf-8") == content, name


@pytest.mark.parametrize("exp", EXPERIMENTS, ids=lambda p: p.name)
def test_outcome_table_order_matches_the_rules(exp):
    classes = outcome_classes((exp / "PREREG.md").read_text(encoding="utf-8"))
    assert classes[0] == "invalid"
    module = f"epmlib.xp.{exp.name[:3]}_{exp.name[4:].replace('-', '_')}"
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError:
        pytest.skip(f"{module} is not implemented yet")
    assert [r.cls for r in mod.RULES] == classes
