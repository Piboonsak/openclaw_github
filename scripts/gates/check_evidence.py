"""Evidence gate: enforce the `.agent/evidence/<TASK>/evidence.md` contract.

Required sections (all present and non-empty):
  ## Commands Executed
  ## Raw Output
  ## Acceptance Criteria

Per-AC rules:
  * Every state AC with `test` set must appear as a checked entry in the
    Acceptance Criteria section AND must have a matching `<test_fn> .* PASSED`
    line in the Raw Output.
  * AC ids that start with `int_` additionally require at least one `docker`
    invocation in Commands Executed.
  * AC without `test` falls back to "section is non-empty" (backward compat).

`status: BLOCKED` states bypass the AC-PASS rule but still require a
`## Blocker` section.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    EVIDENCE_DIR,
    GateError,
    fail,
    load_state,
    resolve_task_id,
)

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
AC_CHECKED_RE_FMT = r"^\s*-\s+\[x\]\s+{ac_id}\b"
DOCKER_RE = re.compile(r"\bdocker\b", re.IGNORECASE)


def parse_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(SECTION_RE.finditer(markdown))
    for idx, m in enumerate(matches):
        title = m.group(1).strip().lower()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        sections[title] = markdown[start:end].strip()
    return sections


def evidence_path(task_id: str) -> Path:
    return EVIDENCE_DIR / task_id / "evidence.md"


def _check_ac(
    ac: dict[str, Any],
    *,
    ac_section: str,
    raw_output: str,
    commands: str,
) -> list[str]:
    errors: list[str] = []
    ac_id = ac["id"]
    test = ac.get("test")
    if not test:
        # Backward-compat: any non-empty AC section is acceptable.
        return errors

    checked_re = re.compile(
        AC_CHECKED_RE_FMT.format(ac_id=re.escape(ac_id)), re.MULTILINE
    )
    if not checked_re.search(ac_section):
        errors.append(
            f"AC '{ac_id}' is not marked complete in Acceptance Criteria "
            f"(expect a line like `- [x] {ac_id} ({test}) -- PASSED`)."
        )
    pass_re = re.compile(rf"{re.escape(test)}.*PASSED", re.IGNORECASE)
    if not pass_re.search(raw_output):
        errors.append(
            f"AC '{ac_id}' test '{test}' has no matching PASSED line in Raw Output."
        )
    if ac_id.startswith("int_") and not DOCKER_RE.search(commands):
        errors.append(
            f"Integration AC '{ac_id}' requires a `docker` command in Commands Executed."
        )
    return errors


def main() -> int:
    print("=== AI Dev Gate: Evidence Contract ===")
    try:
        task_id = resolve_task_id()
        state = load_state(task_id)
    except GateError as exc:
        return fail(str(exc))

    path = evidence_path(task_id)
    print(f"TASK_ID       : {task_id}")
    print(f"Evidence file : {path.relative_to(path.parents[3])}")

    if not path.exists():
        return fail(
            f"Missing evidence file at {path}. "
            f"Create it with sections: Commands Executed, Raw Output, Acceptance Criteria."
        )
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 50:
        return fail(f"Evidence file {path} is too short ({len(text)} bytes).")

    sections = parse_sections(text)
    required = ["commands executed", "raw output", "acceptance criteria"]
    missing = [s for s in required if not sections.get(s)]
    if missing:
        return fail(f"Missing or empty required section(s): {', '.join(missing)}.")

    commands = sections["commands executed"]
    raw_output = sections["raw output"]
    ac_section = sections["acceptance criteria"]

    if state.get("status") == "BLOCKED":
        if not sections.get("blocker"):
            return fail("status=BLOCKED requires a `## Blocker` section.")
        print("BLOCKED override accepted; skipping AC-PASS enforcement.")
        return 0

    errors: list[str] = []
    for ac in state.get("acceptance_criteria") or []:
        errors.extend(
            _check_ac(
                ac,
                ac_section=ac_section,
                raw_output=raw_output,
                commands=commands,
            )
        )

    if errors:
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return fail(f"{len(errors)} evidence contract violation(s) for {task_id}.")

    ac_count = len(state.get("acceptance_criteria") or [])
    print(f"OK: 3 sections present, {ac_count} AC verified against Raw Output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
