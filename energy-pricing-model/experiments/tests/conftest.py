from pathlib import Path

from hypothesis import settings

settings.register_profile("default", derandomize=True, max_examples=200, deadline=None)
settings.register_profile("thorough", max_examples=2000, deadline=None)
settings.load_profile("default")

EXPERIMENTS_DIR = Path(__file__).resolve().parents[1]
