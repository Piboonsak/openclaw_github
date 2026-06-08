"""Tests for `scripts/intake_to_state.py`."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture()
def intake():
    return importlib.import_module("intake_to_state")


VALID_BODY = """### Q1 Task ID

TASK-501

### Q2 Risk tier

MEDIUM

### Q3 Model tier

tier-2a-copilot

### Q4 Allowed scope

src/ocr/**
tests/test_ocr.py

### Q5 Forbidden scope

private_data/**
**/.env*

### Q6 Acceptance criteria

ac_ocr_runs | sample PDF returns text | test_ocr_runs
ac_conf | confidence attached | test_conf

### Q7 Max loops

5

### Q8 Escalation policy

human
"""


def test_parse_q_sections_finds_all(intake):
    sections = intake.parse_q_sections(VALID_BODY)
    assert set(sections.keys()) == {f"Q{i}" for i in range(1, 9)}


def test_build_state_happy(intake):
    state = intake.build_state(VALID_BODY, issue_url="https://example/issues/1")
    assert state["task_id"] == "TASK-501"
    assert state["risk_tier"] == "MEDIUM"
    assert state["model_tier"] == "tier-2a-copilot"
    assert state["allowed_scope"] == ["src/ocr/**", "tests/test_ocr.py"]
    assert state["forbidden_scope"] == ["private_data/**", "**/.env*"]
    assert len(state["acceptance_criteria"]) == 2
    assert state["acceptance_criteria"][0] == {
        "id": "ac_ocr_runs",
        "desc": "sample PDF returns text",
        "test": "test_ocr_runs",
    }
    assert state["max_loops"] == 5
    assert state["escalation_policy"] == "human"
    assert state["status"] == "PENDING"
    assert state["issue_url"] == "https://example/issues/1"


def test_build_state_rejects_missing_acceptance(intake):
    body = VALID_BODY.replace(
        "ac_ocr_runs | sample PDF returns text | test_ocr_runs\nac_conf | confidence attached | test_conf",
        "_No response_",
    )
    with pytest.raises(intake.IntakeError) as exc:
        intake.build_state(body)
    assert any("acceptance_criteria" in m for m in exc.value.messages)


def test_build_state_rejects_bad_task_id(intake):
    body = VALID_BODY.replace("TASK-501", "task-501")
    with pytest.raises(intake.IntakeError) as exc:
        intake.build_state(body)
    assert any("task_id" in m for m in exc.value.messages)


def test_build_state_rejects_bad_risk(intake):
    body = VALID_BODY.replace("MEDIUM", "WHATEVER")
    with pytest.raises(intake.IntakeError) as exc:
        intake.build_state(body)
    assert any("risk_tier" in m for m in exc.value.messages)


def test_build_state_rejects_max_loops_out_of_range(intake):
    body = VALID_BODY.replace("### Q7 Max loops\n\n5", "### Q7 Max loops\n\n99")
    with pytest.raises(intake.IntakeError) as exc:
        intake.build_state(body)
    assert any("max_loops" in m for m in exc.value.messages)


def test_main_writes_state_file(intake, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_BODY, encoding="utf-8")
    out_dir = tmp_path / "state"
    rc = intake.main(["--body", str(body_file), "--out", str(out_dir)])
    assert rc == 0
    state = json.loads((out_dir / "TASK-501.json").read_text(encoding="utf-8"))
    assert state["task_id"] == "TASK-501"


def test_main_writes_rework_comment_on_failure(intake, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_BODY.replace("TASK-501", "bad"), encoding="utf-8")
    out_dir = tmp_path / "state"
    comment_file = tmp_path / "comment.md"
    rc = intake.main(
        [
            "--body",
            str(body_file),
            "--out",
            str(out_dir),
            "--comment-output",
            str(comment_file),
        ]
    )
    assert rc == 1
    assert comment_file.exists()
    assert "validation failed" in comment_file.read_text(encoding="utf-8").lower()
