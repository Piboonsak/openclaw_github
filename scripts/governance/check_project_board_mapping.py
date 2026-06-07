#!/usr/bin/env python3
"""Check project board status-column mapping against expected values.

Usage:
  python scripts/governance/check_project_board_mapping.py \
    --owner YAHWAN-SHOP --project-number 1

Environment:
  GITHUB_TOKEN (required)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any

GRAPHQL_API = "https://api.github.com/graphql"
DEFAULT_COLUMNS = [
    "No Status",
    "Backlog",
    "Investigate",
    "Ready for Trial",
    "In Progress",
    "Review",
    "Done",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate project board status mapping"
    )
    parser.add_argument("--owner", required=True, help="GitHub org/user login")
    parser.add_argument(
        "--project-number", type=int, required=True, help="ProjectV2 number"
    )
    parser.add_argument("--status-field", default="Status", help="Status field name")
    parser.add_argument(
        "--expected",
        nargs="*",
        default=DEFAULT_COLUMNS,
        help="Expected status values in order",
    )
    parser.add_argument(
        "--allow-extra", action="store_true", help="Do not fail on extra status options"
    )
    return parser.parse_args()


def graphql(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_API,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def load_project(token: str, owner: str, number: int) -> dict[str, Any]:
    query = """
    query($owner: String!, $number: Int!) {
      organization(login: $owner) {
        projectV2(number: $number) {
          id
          title
          fields(first: 50) {
            nodes {
              ... on ProjectV2SingleSelectField {
                name
                options {
                  id
                  name
                }
              }
            }
          }
        }
      }
      user(login: $owner) {
        projectV2(number: $number) {
          id
          title
          fields(first: 50) {
            nodes {
              ... on ProjectV2SingleSelectField {
                name
                options {
                  id
                  name
                }
              }
            }
          }
        }
      }
    }
    """
    data = graphql(token, query, {"owner": owner, "number": number})
    org_proj = (data.get("organization") or {}).get("projectV2")
    user_proj = (data.get("user") or {}).get("projectV2")
    project = org_proj or user_proj
    if not project:
        raise RuntimeError(f"ProjectV2 #{number} not found for owner {owner}")
    return project


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("ERROR: GITHUB_TOKEN is required", file=sys.stderr)
        return 2

    project = load_project(token, args.owner, args.project_number)
    fields = project.get("fields", {}).get("nodes", [])
    status_field = next(
        (
            f
            for f in fields
            if isinstance(f, dict) and f.get("name") == args.status_field
        ),
        None,
    )
    if not status_field:
        print(
            f"ERROR: Status field '{args.status_field}' not found in project '{project.get('title')}'",
            file=sys.stderr,
        )
        return 1

    actual = [opt["name"] for opt in status_field.get("options", [])]
    expected = args.expected
    missing = [name for name in expected if name not in actual]
    extra = [name for name in actual if name not in expected]

    order_ok = True
    cursor = -1
    for name in expected:
        if name not in actual:
            order_ok = False
            break
        idx = actual.index(name)
        if idx < cursor:
            order_ok = False
            break
        cursor = idx

    result = {
        "project": project.get("title"),
        "status_field": args.status_field,
        "expected": expected,
        "actual": actual,
        "missing": missing,
        "extra": extra,
        "order_ok": order_ok,
    }
    print(json.dumps(result, ensure_ascii=True, indent=2))

    if missing:
        return 1
    if (not args.allow_extra) and extra:
        return 1
    if not order_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
