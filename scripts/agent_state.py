"""Agent governance state CLI.

Reads, writes, validates `.agent/state/TASK-<ID>.json` files against the schema
in `.agent/state/_schema.json`.

Usage:
    python scripts/agent_state.py validate .agent/state/TASK-501.json
    python scripts/agent_state.py get TASK-501 allowed_scope
    python scripts/agent_state.py init TASK-501 \
        --risk MEDIUM --model tier-2a-copilot \
        --allowed "src/ocr/**" --allowed "tests/test_ocr.py" \
        --forbidden "private_data/**" \
        --ac "ac_ocr_runs|Tesseract returns text|test_ocr_runs_on_sample"
    python scripts/agent_state.py update TASK-501 status IN_PROGRESS
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
except ImportError as exc:  # pragma: no cover - exercised in fresh envs
    sys.stderr.write(
        "ERROR: jsonschema is required. Install via `pip install jsonschema>=4.21`.\n"
    )
    raise SystemExit(2) from exc

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".agent" / "state"
SCHEMA_PATH = STATE_DIR / "_schema.json"

TASK_ID_RE = re.compile(r"^TASK-[A-Z0-9-]+$")
AC_INLINE_RE = re.compile(r"^([a-z][a-z0-9_]*)\|([^|]+?)(?:\|(.+))?$")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state_path(task_id: str) -> Path:
    if not TASK_ID_RE.match(task_id):
        raise SystemExit(
            f"ERROR: invalid task_id '{task_id}' (must match {TASK_ID_RE.pattern})"
        )
    return STATE_DIR / f"{task_id}.json"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_state(task_id_or_path: str) -> dict[str, Any]:
    path = Path(task_id_or_path)
    if not path.exists():
        path = state_path(task_id_or_path)
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any], *, path: Path | None = None) -> Path:
    target = path or state_path(state["task_id"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return target


def validate_state(state: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(state), key=lambda e: list(e.absolute_path))
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in errors
    ]


def parse_ac(values: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in values:
        match = AC_INLINE_RE.match(raw.strip())
        if not match:
            raise SystemExit(
                f"ERROR: --ac value '{raw}' must be 'id|description' or 'id|description|test_fn'"
            )
        ac_id, desc, test = match.groups()
        rows.append(
            {"id": ac_id, "desc": desc.strip(), "test": test.strip() if test else None}
        )
    return rows


def cmd_validate(args: argparse.Namespace) -> int:
    state = load_state(args.target)
    errors = validate_state(state)
    if errors:
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        print(f"FAIL: {len(errors)} schema error(s) in {args.target}", file=sys.stderr)
        return 1
    print(f"OK: {args.target} validates against schema")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    state = load_state(args.task_id)
    if args.field not in state:
        print(f"ERROR: field '{args.field}' not in state", file=sys.stderr)
        return 1
    value = state[args.field]
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(value)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    state = load_state(args.task_id)
    field = args.field
    value: Any = args.value
    if field in {"max_loops", "run_count"}:
        value = int(value)
    elif field in {"allowed_scope", "forbidden_scope", "last_modified_files"}:
        value = json.loads(value)
    elif field == "acceptance_criteria":
        value = json.loads(value)
    state[field] = value
    state["updated_at"] = _now()
    errors = validate_state(state)
    if errors:
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        print("FAIL: update produced invalid state; not saved.", file=sys.stderr)
        return 1
    save_state(state)
    print(f"OK: {args.task_id} {field} updated")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    task_id = args.task_id
    now = _now()
    state: dict[str, Any] = {
        "task_id": task_id,
        "issue_url": args.issue_url,
        "project_item_id": None,
        "status": "PENDING",
        "risk_tier": args.risk,
        "model_tier": args.model,
        "allowed_scope": args.allowed,
        "forbidden_scope": args.forbidden,
        "acceptance_criteria": parse_ac(args.ac),
        "max_loops": args.max_loops,
        "run_count": 0,
        "last_action": "init",
        "last_modified_files": [],
        "blocker_reason": None,
        "escalation_policy": args.escalation,
        "created_at": now,
        "updated_at": now,
    }
    errors = validate_state(state)
    if errors:
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        print("FAIL: init produced invalid state; not saved.", file=sys.stderr)
        return 1
    path = state_path(task_id)
    if path.exists() and not args.force:
        print(
            f"ERROR: {path} already exists. Use --force to overwrite.", file=sys.stderr
        )
        return 1
    save_state(state, path=path)
    print(f"OK: wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agent governance state CLI")
    sub = p.add_subparsers(dest="command", required=True)

    pv = sub.add_parser("validate", help="Validate a state file against the schema.")
    pv.add_argument("target", help="TASK-<ID> or path to state JSON")
    pv.set_defaults(func=cmd_validate)

    pg = sub.add_parser("get", help="Print a field value.")
    pg.add_argument("task_id")
    pg.add_argument("field")
    pg.set_defaults(func=cmd_get)

    pu = sub.add_parser("update", help="Set a field value.")
    pu.add_argument("task_id")
    pu.add_argument("field")
    pu.add_argument("value", help="Plain value, or JSON for array/object fields")
    pu.set_defaults(func=cmd_update)

    pi = sub.add_parser("init", help="Create a new state file.")
    pi.add_argument("task_id")
    pi.add_argument("--issue-url", default=None)
    pi.add_argument(
        "--risk", required=True, choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    )
    pi.add_argument(
        "--model",
        required=True,
        choices=["tier-1-opus", "tier-2a-copilot", "tier-2b-sonnet", "tier-3-gemini"],
    )
    pi.add_argument("--allowed", action="append", required=True, help="Repeatable glob")
    pi.add_argument("--forbidden", action="append", default=[], help="Repeatable glob")
    pi.add_argument(
        "--ac",
        action="append",
        required=True,
        help="Repeatable. Format: 'id|description' or 'id|description|test_fn'",
    )
    pi.add_argument("--max-loops", type=int, default=5)
    pi.add_argument(
        "--escalation", default="human", choices=["human", "ai-debate", "stop"]
    )
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
