"""SIT seed entrypoint with anonymized company defaults.

This wrapper keeps TASK-1306A deployment scripts stable while reusing scripts/seed_data.py.
"""

from __future__ import annotations

import os
from pathlib import Path

from scripts.seed_data import run_seed

REPO_ROOT = Path(__file__).resolve().parents[1]
ANON_COMPANIES = REPO_ROOT / "samples" / "sit" / "companies.anonymized.json"


if __name__ == "__main__":
    os.environ.setdefault("COMPANIES_STORE", str(ANON_COMPANIES))
    stats = run_seed()
    print(stats)
