"""Shared fixtures for governance tests.

Each gate module reads ``STATE_DIR``, ``EVIDENCE_DIR`` and
``MODEL_POLICY_PATH`` from ``scripts.gates._common`` at call time. We override
those to point inside ``tmp_path`` so tests cannot touch the real repo state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
GATES = SCRIPTS / "gates"

# Make `scripts/` and `scripts/gates/` importable in tests.
for p in (str(SCRIPTS), str(GATES)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture()
def gates_env(tmp_path, monkeypatch):
    """Isolate STATE_DIR / EVIDENCE_DIR / MODEL_POLICY_PATH inside tmp_path.

    The gate modules import these names at load time, so we must patch them on
    each gate module in addition to `_common`.
    """
    state_dir = tmp_path / ".agent" / "state"
    evidence_dir = tmp_path / ".agent" / "evidence"
    policy_path = tmp_path / "config" / "model-policy.yaml"
    state_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        "safety:\n  forbidden_paths:\n    - 'private_data/**'\n    - '**/.env*'\n",
        encoding="utf-8",
    )

    import _common  # type: ignore  # noqa: E402

    monkeypatch.setattr(_common, "STATE_DIR", state_dir)
    monkeypatch.setattr(_common, "EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(_common, "MODEL_POLICY_PATH", policy_path)

    # Patch the same names on any gate module that already imported them.
    for mod_name in ("check_scope", "check_evidence", "min_action_check"):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            for attr, value in (
                ("STATE_DIR", state_dir),
                ("EVIDENCE_DIR", evidence_dir),
                ("MODEL_POLICY_PATH", policy_path),
            ):
                if hasattr(mod, attr):
                    monkeypatch.setattr(mod, attr, value)

    return {
        "tmp_path": tmp_path,
        "state_dir": state_dir,
        "evidence_dir": evidence_dir,
        "policy_path": policy_path,
    }


@pytest.fixture()
def sample_state():
    return {
        "task_id": "TASK-501",
        "status": "PENDING",
        "risk_tier": "MEDIUM",
        "model_tier": "tier-2a-copilot",
        "allowed_scope": [
            "src/ocr/**",
            "tests/test_ocr.py",
            ".agent/evidence/TASK-501/**",
            ".agent/state/TASK-501.json",
        ],
        "forbidden_scope": ["src/api/**", "src/backend/**"],
        "acceptance_criteria": [
            {"id": "ac_ocr_runs", "desc": "OCR runs", "test": "test_ocr_runs"},
            {"id": "ac_conf", "desc": "confidence attached", "test": "test_conf"},
        ],
        "max_loops": 5,
        "run_count": 0,
        "last_action": "init",
        "escalation_policy": "human",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture()
def write_state(gates_env, sample_state):
    """Return a callable that writes a state file under the isolated STATE_DIR."""

    def _write(state: dict | None = None, task_id: str = "TASK-501"):
        payload = dict(sample_state if state is None else state)
        payload["task_id"] = task_id
        path = gates_env["state_dir"] / f"{task_id}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    return _write
