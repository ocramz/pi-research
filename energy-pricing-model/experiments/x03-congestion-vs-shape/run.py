"""x03-congestion-vs-shape: run the registered config (PREREG.md). The work is in
epmlib.xp.x03_congestion_vs_shape; `--help` lists the options."""

import os
import sys
from pathlib import Path

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_var] = "1"  # one BLAS thread per process: results must not depend on --workers

from epmlib.xp.x03_congestion_vs_shape import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], Path(__file__).resolve().parent))
