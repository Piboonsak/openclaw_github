"""Shared helpers for `scripts/gates/*` governance gates.

Pure stdlib so it can run in any CI environment without extra installs
(jsonschema is needed only for schema validation, not for gate execution).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = REPO_ROOT / ".agent" / "state"
EVIDENCE_DIR = REPO_ROOT / ".agent" / "evidence"
MODEL_POLICY_PATH = REPO_ROOT / "config" / "model-policy.yaml"

TASK_ID_RE = re.compile(r"\b(TASK-[A-Z0-9-]+)\b")
TASK_BRANCH_RE = re.compile(r"task-([A-Z0-9-]+)", re.IGNORECASE)


class GateError(RuntimeError):
    """Raised when a gate hits an unrecoverable configuration issue."""


def resolve_task_id() -> str:
    """Resolve the active TASK-<ID> from env or branch name.

    Resolution order:
      1. `TASK_ID` env var (CI step or local export).
      2. PR_TITLE env var (set by agent_gate.yml from `${{ github.event.pull_request.title }}`).
      3. GITHUB_HEAD_REF / GITHUB_REF_NAME / current branch -> `task-<id>/...` pattern.
    """
    explicit = os.environ.get("TASK_ID")
    if explicit:
        return explicit.strip().upper()

    pr_title = os.environ.get("PR_TITLE", "")
    match = TASK_ID_RE.search(pr_title.upper())
    if match:
        return match.group(1)

    branch = (
        os.environ.get("GITHUB_HEAD_REF")
        or os.environ.get("GITHUB_REF_NAME")
        or _current_branch()
    )
    if branch:
        match = TASK_BRANCH_RE.search(branch)
        if match:
            return f"TASK-{match.group(1).upper()}"

    raise GateError(
        "Cannot resolve TASK_ID. Set TASK_ID env var, name PR 'TASK-<ID>: ...', "
        "or use a branch like 'task-501/...'."
    )


def _current_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
        ).strip()
    except Exception:  # pragma: no cover - best effort
        return ""


def load_state(task_id: str) -> dict[str, Any]:
    path = STATE_DIR / f"{task_id}.json"
    if not path.exists():
        raise GateError(
            f"State file not found: {path.relative_to(REPO_ROOT)}. "
            "Run `python scripts/agent_state.py init {task_id} ...` or open a Q1-Q8 intake issue."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_global_forbidden() -> list[str]:
    """Read `safety.forbidden_paths` from config/model-policy.yaml.

    Uses PyYAML if available; otherwise a minimal regex extraction (good enough
    for the flat list we ship).
    """
    if not MODEL_POLICY_PATH.exists():
        return []
    text = MODEL_POLICY_PATH.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        paths = (data.get("safety") or {}).get("forbidden_paths") or []
        return [str(p) for p in paths]
    except ImportError:
        return _extract_forbidden_paths_regex(text)


def _extract_forbidden_paths_regex(text: str) -> list[str]:
    paths: list[str] = []
    in_block = False
    for raw in text.splitlines():
        if raw.strip().startswith("forbidden_paths:"):
            in_block = True
            continue
        if in_block:
            stripped = raw.strip()
            if stripped.startswith("- "):
                value = stripped[2:].strip()
                if value.startswith(("'", '"')) and value.endswith(("'", '"')):
                    value = value[1:-1]
                paths.append(value)
            else:
                break
    return paths


def changed_files(base: str = "origin/main") -> list[str]:
    """Return the list of files changed on the current branch vs. ``base``."""
    candidates: list[list[str]] = [
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        ["git", "diff", "--name-only", "main"],
        ["git", "diff", "--name-only", "HEAD~1"],
    ]
    for cmd in candidates:
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            files = [line.strip() for line in out.splitlines() if line.strip()]
            if files:
                return files
        except subprocess.CalledProcessError:
            continue
        except FileNotFoundError:
            break
    return []


def staged_files() -> list[str]:
    """Return the list of currently staged files (for pre-commit hooks)."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], text=True
        )
    except Exception:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def match_any(path: str, patterns: Iterable[str]) -> bool:
    """Return True if ``path`` matches any of the glob ``patterns`` (POSIX style).

    Supports ``**`` recursive match in addition to standard fnmatch behaviour.
    """
    normalised = path.replace("\\", "/")
    for raw in patterns:
        if not raw:
            continue
        pattern = raw.replace("\\", "/")
        if _glob_match(normalised, pattern):
            return True
    return False


def _glob_match(path: str, pattern: str) -> bool:
    if "**" in pattern:
        # Translate `a/**/b` to a regex; fnmatch alone treats `**` as `*`.
        regex_parts: list[str] = []
        for part in pattern.split("/"):
            if part == "**":
                regex_parts.append(".*")
            else:
                regex_parts.append(fnmatch.translate(part).rstrip("\\Z").rstrip("$"))
        regex = "^" + "/".join(regex_parts) + "$"
        return re.match(regex, path) is not None
    return fnmatch.fnmatchcase(path, pattern)


def fail(message: str, *, code: int = 1) -> "int":
    """Print an error message to stderr and return the exit code."""
    print(f"FAIL: {message}", file=sys.stderr)
    return code
