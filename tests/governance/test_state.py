"""Tests for `.agent/state/_schema.json` and `scripts/agent_state.py`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / ".agent" / "state" / "_schema.json"
SEED_PATH = REPO_ROOT / ".agent" / "state" / "TASK-501.json"


def _schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(_schema())


def test_seed_state_validates():
    if not SEED_PATH.exists():
        pytest.skip("seed state file not present")
    validator = Draft202012Validator(_schema())
    state = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    errors = sorted(validator.iter_errors(state), key=lambda e: list(e.absolute_path))
    assert not errors, [e.message for e in errors]


def test_schema_requires_allowed_scope_non_empty(sample_state):
    bad = dict(sample_state)
    bad["allowed_scope"] = []
    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(bad))
    assert any(
        "allowed_scope" in (list(e.absolute_path) or [str(e.message)])
        or "shortest than" not in e.message
        for e in errors
    )
    assert errors


def test_schema_rejects_bad_task_id(sample_state):
    bad = dict(sample_state)
    bad["task_id"] = "task-501"  # lower-case prefix not allowed
    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(bad))
    assert errors


def test_schema_rejects_bad_status(sample_state):
    bad = dict(sample_state)
    bad["status"] = "FINISHED"
    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(bad))
    assert errors


def test_schema_rejects_max_loops_zero(sample_state):
    bad = dict(sample_state)
    bad["max_loops"] = 0
    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(bad))
    assert errors


def test_schema_rejects_bad_ac_id(sample_state):
    bad = dict(sample_state)
    bad["acceptance_criteria"] = [{"id": "Bad-AC", "desc": "no", "test": "t"}]
    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(bad))
    assert errors
