"""Scope gate: enforce allowed_scope / forbidden_scope from the active TASK state.

Run order:
  1. Resolve TASK_ID from env, PR title, or branch.
  2. Load `.agent/state/<TASK_ID>.json`.
  3. Merge per-task `forbidden_scope` with global `safety.forbidden_paths`
     from `config/model-policy.yaml`.
  4. For each changed file (vs. origin/main):
       - HARD-FAIL if it matches any forbidden glob.
       - HARD-FAIL if it does NOT match any allowed glob.
  5. Otherwise: print summary and exit 0.

Skipping forbidden paths is NEVER allowed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402  (path-injected import)
    GateError,
    changed_files,
    fail,
    load_global_forbidden,
    load_state,
    match_any,
    resolve_task_id,
)


def main() -> int:
    print("=== AI Dev Gate: Scope Compliance (state-aware) ===")
    try:
        task_id = resolve_task_id()
        state = load_state(task_id)
    except GateError as exc:
        return fail(str(exc))

    allowed = list(state.get("allowed_scope") or [])
    per_task_forbidden = list(state.get("forbidden_scope") or [])
    global_forbidden = load_global_forbidden()
    forbidden = sorted(set(per_task_forbidden + global_forbidden))

    if not allowed:
        return fail(f"State {task_id} has empty allowed_scope.")

    files = changed_files()
    if not files:
        print(f"No changed files detected for {task_id}; gate passes vacuously.")
        return 0

    print(f"TASK_ID            : {task_id}")
    print(f"Changed files ({len(files)}):")
    for f in files:
        print(f"  - {f}")
    print(f"Allowed scope ({len(allowed)}):")
    for g in allowed:
        print(f"  + {g}")
    print(f"Forbidden scope ({len(forbidden)}, task + global):")
    for g in forbidden:
        print(f"  - {g}")

    forbidden_hits: list[tuple[str, str]] = []
    out_of_scope: list[str] = []
    for path in files:
        for pattern in forbidden:
            if match_any(path, [pattern]):
                forbidden_hits.append((path, pattern))
                break
        if forbidden_hits and forbidden_hits[-1][0] == path:
            continue
        if not match_any(path, allowed):
            out_of_scope.append(path)

    if forbidden_hits:
        for path, pattern in forbidden_hits:
            print(
                f"  X FORBIDDEN: '{path}' matched '{pattern}' (private_data / secrets / out-of-policy).",
                file=sys.stderr,
            )
    if out_of_scope:
        for path in out_of_scope:
            print(
                f"  X OUT-OF-SCOPE: '{path}' not in allowed_scope for {task_id}.",
                file=sys.stderr,
            )

    if forbidden_hits or out_of_scope:
        return fail(
            f"Scope gate blocked {len(forbidden_hits)} forbidden + {len(out_of_scope)} out-of-scope file(s)."
        )

    print(
        f"OK: all {len(files)} file(s) are inside allowed_scope and clear of forbidden paths."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
