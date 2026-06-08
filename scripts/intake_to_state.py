"""Parse a Q1-Q8 intake issue body into a `.agent/state/TASK-<ID>.json` file.

Designed for `.github/workflows/intake-sync.yml`:

  python scripts/intake_to_state.py \
      --event "$GITHUB_EVENT_PATH" \
      --out .agent/state \
      --comment-output comment.md

For local runs:

  python scripts/intake_to_state.py --body issue-body.md --out .agent/state

Exit codes:
  0  state file written
  1  validation failure (a `needs-rework` comment is written to --comment-output)
  2  unrecoverable parser error (bad input file etc.)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover
    sys.stderr.write("ERROR: jsonschema>=4.21 is required.\n")
    raise SystemExit(2) from exc

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / ".agent" / "state" / "_schema.json"

# Match GitHub-issue-form rendered headings exactly: `### Q4 Allowed scope`
Q_HEADING_RE = re.compile(r"^#{2,3}\s+(Q[1-8])\s+([^\n]+?)\s*$", re.MULTILINE)

TASK_ID_RE = re.compile(r"^TASK-[A-Z0-9-]+$")
AC_LINE_RE = re.compile(r"^([a-z][a-z0-9_]*)\s*\|\s*([^|]+?)(?:\s*\|\s*(.+))?$")

VALID_RISK = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_MODEL = {"tier-1-opus", "tier-2a-copilot", "tier-2b-sonnet", "tier-3-gemini"}
VALID_ESCALATION = {"human", "ai-debate", "stop"}


class IntakeError(Exception):
    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_q_sections(body: str) -> dict[str, str]:
    """Return a dict keyed by Q-number (e.g. `Q1`) containing section body."""
    out: dict[str, str] = {}
    matches = list(Q_HEADING_RE.finditer(body))
    for idx, m in enumerate(matches):
        qkey = m.group(1).upper()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        out[qkey] = body[start:end].strip()
    return out


def _clean_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and line.strip() != "_No response_"
    ]


def _parse_ac_lines(text: str, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in _clean_lines(text):
        m = AC_LINE_RE.match(line)
        if not m:
            errors.append(
                f"Q6 Acceptance criteria: cannot parse line '{line}'. "
                "Expected `id | description` or `id | description | test_fn`."
            )
            continue
        ac_id, desc, test = m.groups()
        rows.append(
            {"id": ac_id, "desc": desc.strip(), "test": test.strip() if test else None}
        )
    return rows


def build_state(body: str, *, issue_url: str | None = None) -> dict[str, Any]:
    sections = parse_q_sections(body)
    errors: list[str] = []

    required = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"}
    missing = sorted(required - sections.keys())
    if missing:
        errors.append(f"Missing required Q section(s): {', '.join(missing)}.")
        raise IntakeError(errors)

    task_id = sections["Q1"].strip().splitlines()[0].strip()
    if not TASK_ID_RE.match(task_id):
        errors.append(
            f"Q1 task_id '{task_id}' must match `TASK-<ID>` (uppercase letters/digits/dashes)."
        )

    risk = sections["Q2"].strip().splitlines()[0].strip().upper()
    if risk not in VALID_RISK:
        errors.append(f"Q2 risk_tier '{risk}' must be one of {sorted(VALID_RISK)}.")

    model = sections["Q3"].strip().splitlines()[0].strip()
    if model not in VALID_MODEL:
        errors.append(f"Q3 model_tier '{model}' must be one of {sorted(VALID_MODEL)}.")

    allowed = _clean_lines(sections["Q4"])
    if not allowed:
        errors.append("Q4 allowed_scope must have at least one glob.")

    forbidden = _clean_lines(sections["Q5"])
    if not forbidden:
        errors.append("Q5 forbidden_scope must have at least one glob.")

    acceptance = _parse_ac_lines(sections["Q6"], errors)
    if not acceptance:
        errors.append("Q6 acceptance_criteria must have at least one AC line.")

    max_loops_raw = (
        sections["Q7"].strip().splitlines()[0].strip() if sections["Q7"] else ""
    )
    try:
        max_loops = int(max_loops_raw)
        if not (1 <= max_loops <= 20):
            raise ValueError
    except ValueError:
        errors.append(f"Q7 max_loops '{max_loops_raw}' must be an integer 1-20.")
        max_loops = 5

    escalation = sections["Q8"].strip().splitlines()[0].strip().lower()
    if escalation not in VALID_ESCALATION:
        errors.append(
            f"Q8 escalation_policy '{escalation}' must be one of {sorted(VALID_ESCALATION)}."
        )

    if errors:
        raise IntakeError(errors)

    now = _now()
    state: dict[str, Any] = {
        "task_id": task_id,
        "issue_url": issue_url,
        "project_item_id": None,
        "status": "PENDING",
        "risk_tier": risk,
        "model_tier": model,
        "allowed_scope": allowed,
        "forbidden_scope": forbidden,
        "acceptance_criteria": acceptance,
        "max_loops": max_loops,
        "run_count": 0,
        "last_action": "intake",
        "last_modified_files": [],
        "blocker_reason": None,
        "escalation_policy": escalation,
        "created_at": now,
        "updated_at": now,
    }

    schema_errors = _validate(state)
    if schema_errors:
        raise IntakeError([f"Schema: {e}" for e in schema_errors])

    return state


def _validate(state: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(
        json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    )
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(
            validator.iter_errors(state), key=lambda e: list(e.absolute_path)
        )
    ]


def _write_comment(path: Path, lines: list[str]) -> None:
    body = "### TASK intake validation failed\n\n"
    body += "The Q1-Q8 issue body could not be parsed into a state file.\n\n"
    for line in lines:
        body += f"- {line}\n"
    body += (
        "\nFix the items above and edit the issue. The `intake-sync.yml` workflow "
        "will re-run on edit.\n"
    )
    path.write_text(body, encoding="utf-8")


def _read_body(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.event:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        issue = event.get("issue") or {}
        return _strip_bom(issue.get("body") or ""), issue.get("html_url")
    if args.body:
        return _strip_bom(Path(args.body).read_text(encoding="utf-8")), args.issue_url
    return _strip_bom(sys.stdin.read()), args.issue_url


def _strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse Q1-Q8 intake body to state file."
    )
    parser.add_argument("--event", help="Path to GitHub event JSON (GITHUB_EVENT_PATH)")
    parser.add_argument("--body", help="Path to raw issue body Markdown")
    parser.add_argument("--issue-url", default=None)
    parser.add_argument("--out", default=str(REPO_ROOT / ".agent" / "state"))
    parser.add_argument(
        "--comment-output",
        default=None,
        help="Where to write the rework comment on failure",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        body, issue_url = _read_body(args)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not body.strip():
        print("ERROR: empty issue body", file=sys.stderr)
        return 2

    try:
        state = build_state(body, issue_url=issue_url)
    except IntakeError as exc:
        for line in exc.messages:
            print(f"  - {line}", file=sys.stderr)
        if args.comment_output:
            _write_comment(Path(args.comment_output), exc.messages)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{state['task_id']}.json"

    if args.dry_run:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        print(f"DRY-RUN: would write {out_path}")
        return 0

    out_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"OK: wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
