"""Tests for `scripts/min_action_check.py`."""

from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture()
def min_action():
    return importlib.import_module("min_action_check")


@pytest.fixture()
def common():
    return importlib.import_module("_common")


def test_passes_with_real_src_change(monkeypatch, min_action):
    monkeypatch.setattr(
        min_action,
        "staged_files",
        lambda: ["src/ocr/parser.py", ".agent/state/TASK-501.json"],
    )
    assert min_action.main() == 0


def test_passes_with_test_only_change(monkeypatch, min_action):
    monkeypatch.setattr(min_action, "staged_files", lambda: ["tests/test_ocr.py"])
    assert min_action.main() == 0


def test_blocks_plan_only_commit(monkeypatch, min_action):
    monkeypatch.setattr(
        min_action,
        "staged_files",
        lambda: [
            ".agent/state/TASK-501.json",
            ".agent/evidence/TASK-501/evidence.md",
            "README.md",
        ],
    )
    assert min_action.main() == 1


def test_passes_with_no_staged_files(monkeypatch, min_action):
    monkeypatch.setattr(min_action, "staged_files", lambda: [])
    assert min_action.main() == 0


def test_blocked_override(monkeypatch, gates_env, sample_state, min_action):
    state = dict(sample_state)
    state["status"] = "BLOCKED"
    (gates_env["state_dir"] / "TASK-501.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    evidence_dir = gates_env["evidence_dir"] / "TASK-501"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "evidence.md").write_text(
        "# Evidence\n\n## Blocker\nWaiting on data.\n", encoding="utf-8"
    )

    monkeypatch.setattr(min_action, "STATE_DIR", gates_env["state_dir"])
    monkeypatch.setattr(min_action, "EVIDENCE_DIR", gates_env["evidence_dir"])
    monkeypatch.setattr(
        min_action,
        "staged_files",
        lambda: [".agent/state/TASK-501.json", ".agent/evidence/TASK-501/evidence.md"],
    )
    assert min_action.main() == 0


def test_blocked_override_requires_blocker_section(
    monkeypatch, gates_env, sample_state, min_action
):
    state = dict(sample_state)
    state["status"] = "BLOCKED"
    (gates_env["state_dir"] / "TASK-501.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    evidence_dir = gates_env["evidence_dir"] / "TASK-501"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "evidence.md").write_text(
        "# Evidence -- no blocker section\n", encoding="utf-8"
    )

    monkeypatch.setattr(min_action, "STATE_DIR", gates_env["state_dir"])
    monkeypatch.setattr(min_action, "EVIDENCE_DIR", gates_env["evidence_dir"])
    monkeypatch.setattr(
        min_action, "staged_files", lambda: [".agent/state/TASK-501.json"]
    )
    assert min_action.main() == 1
