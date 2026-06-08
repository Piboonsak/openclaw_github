"""Pre-commit "Action Lock": block plan-only commits.

Pass conditions (any one):
  * At least one staged file matches:
      src/**, tests/**, scripts/**, config/**, docker/**
  * The current task state has status=BLOCKED AND
    `.agent/evidence/<TASK_ID>/evidence.md` contains a `## Blocker` section.

Fail conditions:
  * Staged set is only `.agent/state/**`, `.agent/logs/**`, or `**/*.md` with
    no real code/test/scripts/config/docker file present.

The lock prevents the agent from "looking productive" by committing plans,
logs, or markdown-only changes without backing them with code or tests.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "gates"))

from _common import EVIDENCE_DIR, STATE_DIR, staged_files  # noqa: E402

ACTION_PATTERNS = [
    re.compile(r"^src/"),
    re.compile(r"^tests/"),
    re.compile(r"^scripts/"),
    re.compile(r"^config/"),
    re.compile(r"^docker/"),
]

PASSIVE_PATTERNS = [
    re.compile(r"^\.agent/state/"),
    re.compile(r"^\.agent/logs/"),
    re.compile(r"^\.agent/evidence/"),
    re.compile(r"\.md$", re.IGNORECASE),
]


def _is_action(path: str) -> bool:
    return any(p.search(path) for p in ACTION_PATTERNS)


def _is_passive(path: str) -> bool:
    return any(p.search(path) for p in PASSIVE_PATTERNS)


def _blocked_override() -> tuple[bool, str]:
    """Allow plan/state-only commit when a known task is explicitly BLOCKED."""
    if not STATE_DIR.exists():
        return False, "no state dir"
    candidates = sorted(STATE_DIR.glob("TASK-*.json"))
    if not candidates:
        return False, "no task state files"
    import json

    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("status") != "BLOCKED":
            continue
        task_id = data.get("task_id", path.stem)
        evidence = EVIDENCE_DIR / task_id / "evidence.md"
        if evidence.exists() and "## Blocker" in evidence.read_text(encoding="utf-8"):
            return True, f"{task_id} BLOCKED with ## Blocker section"
    return False, "no BLOCKED task with blocker evidence"


def main() -> int:
    print("=== AI Dev Hook: Action Lock (min_action_check) ===")
    files = staged_files()
    if not files:
        print("OK: no staged files (commit is empty); pass-through.")
        return 0

    actionable = [f for f in files if _is_action(f)]
    passive_only = all(_is_passive(f) for f in files)

    print(f"Staged ({len(files)} file(s)):")
    for f in files:
        kind = "ACTION" if _is_action(f) else ("PASSIVE" if _is_passive(f) else "OTHER")
        print(f"  [{kind}] {f}")

    if actionable:
        print(f"OK: {len(actionable)} action file(s) present.")
        return 0

    if passive_only:
        override, reason = _blocked_override()
        if override:
            print(f"OK: BLOCKED override accepted ({reason}).")
            return 0
        print(
            "FAIL: commit contains only plan/state/log/markdown changes.\n"
            "      Add at least one file under src/**, tests/**, scripts/**, "
            "config/**, or docker/**.\n"
            "      Or set the task status to BLOCKED with a `## Blocker` "
            "section in evidence.md.",
            file=sys.stderr,
        )
        return 1

    print(
        "FAIL: no actionable file (src/tests/scripts/config/docker) is staged.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
