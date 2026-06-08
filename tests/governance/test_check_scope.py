"""Tests for `scripts/gates/check_scope.py`."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def check_scope():
    return importlib.import_module("check_scope")


@pytest.fixture()
def common():
    return importlib.import_module("_common")


def _set_task(monkeypatch, task_id="TASK-501"):
    monkeypatch.setenv("TASK_ID", task_id)


def test_scope_passes_for_in_scope_files(
    monkeypatch, capsys, write_state, check_scope, common
):
    write_state()
    _set_task(monkeypatch)
    monkeypatch.setattr(
        common, "changed_files", lambda *_: ["src/ocr/parser.py", "tests/test_ocr.py"]
    )
    monkeypatch.setattr(check_scope, "changed_files", common.changed_files)
    rc = check_scope.main()
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_scope_blocks_forbidden_private_data(
    monkeypatch, capsys, write_state, check_scope, common
):
    write_state()
    _set_task(monkeypatch)
    monkeypatch.setattr(common, "changed_files", lambda *_: ["private_data/leak.csv"])
    monkeypatch.setattr(check_scope, "changed_files", common.changed_files)
    rc = check_scope.main()
    assert rc != 0
    captured = capsys.readouterr()
    assert "FORBIDDEN" in captured.err or "FORBIDDEN" in captured.out


def test_scope_blocks_forbidden_env_file(monkeypatch, write_state, check_scope, common):
    write_state()
    _set_task(monkeypatch)
    monkeypatch.setattr(common, "changed_files", lambda *_: ["src/ocr/.env.prod"])
    monkeypatch.setattr(check_scope, "changed_files", common.changed_files)
    rc = check_scope.main()
    assert rc != 0


def test_scope_blocks_per_task_forbidden(monkeypatch, write_state, check_scope, common):
    write_state()
    _set_task(monkeypatch)
    monkeypatch.setattr(common, "changed_files", lambda *_: ["src/api/router.py"])
    monkeypatch.setattr(check_scope, "changed_files", common.changed_files)
    rc = check_scope.main()
    assert rc != 0


def test_scope_blocks_out_of_scope_file(monkeypatch, write_state, check_scope, common):
    write_state()
    _set_task(monkeypatch)
    monkeypatch.setattr(common, "changed_files", lambda *_: ["src/frontend/App.tsx"])
    monkeypatch.setattr(check_scope, "changed_files", common.changed_files)
    rc = check_scope.main()
    assert rc != 0


def test_scope_passes_vacuously_with_no_changes(
    monkeypatch, write_state, check_scope, common
):
    write_state()
    _set_task(monkeypatch)
    monkeypatch.setattr(common, "changed_files", lambda *_: [])
    monkeypatch.setattr(check_scope, "changed_files", common.changed_files)
    assert check_scope.main() == 0
