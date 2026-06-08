"""Compatibility shim. Forwards to scripts/gates/check_evidence.py.

The contract-enforcing evidence gate (3 sections + AC-to-test PASS binding)
lives in `scripts/gates/check_evidence.py`. This file is kept so existing
CI steps and docs that reference `scripts/check_evidence.py` keep working.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parent / "gates" / "check_evidence.py"

if __name__ == "__main__":
    sys.argv[0] = str(GATE)
    runpy.run_path(str(GATE), run_name="__main__")
