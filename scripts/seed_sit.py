"""SIT seed entrypoint with anonymized company defaults.

This wrapper keeps TASK-1306A deployment scripts stable while reusing scripts/seed_data.py.
"""

from __future__ import annotations

import os
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
ANON_COMPANIES = REPO_ROOT / "samples" / "sit" / "companies.anonymized.json"


def _load_run_seed():
    module_path = SCRIPTS_DIR / "seed_data.py"
    spec = importlib.util.spec_from_file_location("seed_data", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_seed


if __name__ == "__main__":
    os.environ.setdefault("COMPANIES_STORE", str(ANON_COMPANIES))
    run_seed = _load_run_seed()
    stats = run_seed()
    print(stats)
