"""Tests for `scripts/gates/check_evidence.py`."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def check_evidence():
    return importlib.import_module("check_evidence")


@pytest.fixture()
def common():
    return importlib.import_module("_common")


VALID_EVIDENCE = """# Evidence for TASK-501

## Commands Executed
```
pytest tests/test_ocr.py -q
```

## Raw Output
```
test_ocr_runs PASSED
test_conf PASSED
```

## Acceptance Criteria
- [x] ac_ocr_runs (test_ocr_runs) -- PASSED
- [x] ac_conf (test_conf) -- PASSED
"""


def _write_evidence(env, body: str, task_id: str = "TASK-501"):
    dir_ = env["evidence_dir"] / task_id
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "evidence.md").write_text(body, encoding="utf-8")


def test_evidence_passes_for_complete_file(
    monkeypatch, write_state, gates_env, check_evidence
):
    write_state()
    _write_evidence(gates_env, VALID_EVIDENCE)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() == 0


def test_evidence_missing_file_fails(monkeypatch, write_state, check_evidence):
    write_state()
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() != 0


def test_evidence_missing_section_fails(
    monkeypatch, write_state, gates_env, check_evidence
):
    write_state()
    body = VALID_EVIDENCE.replace("## Raw Output", "## Raw Logs")
    _write_evidence(gates_env, body)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() != 0


def test_evidence_missing_passed_line_fails(
    monkeypatch, write_state, gates_env, check_evidence
):
    write_state()
    body = VALID_EVIDENCE.replace("test_ocr_runs PASSED", "test_ocr_runs FAILED")
    _write_evidence(gates_env, body)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() != 0


def test_evidence_unchecked_ac_fails(
    monkeypatch, write_state, gates_env, check_evidence
):
    write_state()
    body = VALID_EVIDENCE.replace("- [x] ac_ocr_runs", "- [ ] ac_ocr_runs")
    _write_evidence(gates_env, body)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() != 0


def test_evidence_int_prefix_requires_docker(
    monkeypatch, sample_state, write_state, gates_env, check_evidence
):
    state = dict(sample_state)
    state["acceptance_criteria"] = [
        {"id": "int_pipeline", "desc": "end to end", "test": "test_pipeline"},
    ]
    write_state(state)
    body = """# Evidence

## Commands Executed
```
pytest tests/test_pipeline.py
```

## Raw Output
```
test_pipeline PASSED
```

## Acceptance Criteria
- [x] int_pipeline (test_pipeline) -- PASSED
"""
    _write_evidence(gates_env, body)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    # Missing docker => fail
    assert check_evidence.main() != 0

    body_with_docker = body.replace(
        "pytest tests/test_pipeline.py",
        "docker compose up -d\npytest tests/test_pipeline.py",
    )
    _write_evidence(gates_env, body_with_docker)
    assert check_evidence.main() == 0


def test_blocked_status_skips_ac_check(
    monkeypatch, sample_state, write_state, gates_env, check_evidence
):
    state = dict(sample_state)
    state["status"] = "BLOCKED"
    write_state(state)
    body = """# Evidence

## Commands Executed
```
nothing -- blocked
```

## Raw Output
```
n/a
```

## Acceptance Criteria
- [ ] ac_ocr_runs (test_ocr_runs)
- [ ] ac_conf (test_conf)

## Blocker
Waiting on sample dataset from owner.
"""
    _write_evidence(gates_env, body)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() == 0


def test_blocked_without_blocker_section_fails(
    monkeypatch, sample_state, write_state, gates_env, check_evidence
):
    state = dict(sample_state)
    state["status"] = "BLOCKED"
    write_state(state)
    body = VALID_EVIDENCE  # no `## Blocker`
    _write_evidence(gates_env, body)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() != 0


def test_backward_compat_ac_without_test(
    monkeypatch, sample_state, write_state, gates_env, check_evidence
):
    state = dict(sample_state)
    state["acceptance_criteria"] = [
        {"id": "ac_docs", "desc": "docs updated"},  # no test field
    ]
    write_state(state)
    body = """# Evidence

## Commands Executed
```
mkdocs build
```

## Raw Output
```
ok
```

## Acceptance Criteria
- ac_docs: docs updated and reviewed manually
"""
    _write_evidence(gates_env, body)
    monkeypatch.setenv("TASK_ID", "TASK-501")
    assert check_evidence.main() == 0
