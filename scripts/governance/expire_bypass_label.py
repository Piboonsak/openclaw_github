#!/usr/bin/env python3
"""Auto-expire `bypass:governance` labels older than a threshold.

Usage:
  python scripts/governance/expire_bypass_label.py --hours 24

Environment:
  GITHUB_TOKEN (required)
  GITHUB_REPOSITORY=owner/repo (required, e.g. YAHWAN-SHOP/ai-accounting-copilot)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

API_BASE = "https://api.github.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expire stale bypass labels on open PRs"
    )
    parser.add_argument(
        "--label", default="bypass:governance", help="Label name to expire"
    )
    parser.add_argument("--hours", type=int, default=24, help="Max label age in hours")
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not mutate labels/comments"
    )
    return parser.parse_args()


def github_request(
    token: str, method: str, url: str, body: dict[str, Any] | None = None
) -> tuple[int, Any, dict[str, str]]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req) as resp:
        payload = resp.read().decode("utf-8")
        parsed = json.loads(payload) if payload else None
        return resp.getcode(), parsed, dict(resp.headers)


def iter_paginated(token: str, url: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    next_url = url
    while next_url:
        _, data, headers = github_request(token, "GET", next_url)
        if isinstance(data, list):
            items.extend(data)
        link = headers.get("Link", "")
        next_url = ""
        for part in link.split(","):
            if 'rel="next"' in part:
                start = part.find("<")
                end = part.find(">")
                if start != -1 and end != -1:
                    next_url = part[start + 1 : end]
        if not link:
            break
    return items


def parse_iso8601(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def find_last_labeled_at(
    timeline: list[dict[str, Any]], label_name: str
) -> dt.datetime | None:
    latest: dt.datetime | None = None
    for event in timeline:
        if event.get("event") != "labeled":
            continue
        label = event.get("label") or {}
        if label.get("name") != label_name:
            continue
        created_at = event.get("created_at")
        if not created_at:
            continue
        timestamp = parse_iso8601(created_at)
        if latest is None or timestamp > latest:
            latest = timestamp
    return latest


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if not token:
        print("ERROR: GITHUB_TOKEN is required", file=sys.stderr)
        return 2
    if not repository or "/" not in repository:
        print("ERROR: GITHUB_REPOSITORY must be owner/repo", file=sys.stderr)
        return 2

    owner, repo = repository.split("/", 1)
    encoded_label = urllib.parse.quote(args.label, safe="")
    issue_list_url = (
        f"{API_BASE}/repos/{owner}/{repo}/issues"
        f"?state=open&labels={encoded_label}&per_page=100"
    )
    issues = iter_paginated(token, issue_list_url)

    now = dt.datetime.now(dt.timezone.utc)
    threshold = dt.timedelta(hours=args.hours)
    expired = 0

    for issue in issues:
        if "pull_request" not in issue:
            continue
        number = issue["number"]
        timeline_url = (
            f"{API_BASE}/repos/{owner}/{repo}/issues/{number}/timeline?per_page=100"
        )
        timeline = iter_paginated(token, timeline_url)
        labeled_at = find_last_labeled_at(timeline, args.label)
        if labeled_at is None:
            continue

        age = now - labeled_at
        if age <= threshold:
            continue

        expired += 1
        print(f"PR #{number}: label age {age} > {threshold} -> expire")
        if args.dry_run:
            continue

        remove_url = (
            f"{API_BASE}/repos/{owner}/{repo}/issues/{number}/labels/{encoded_label}"
        )
        github_request(token, "DELETE", remove_url)

        comment_body = {
            "body": (
                f"Auto-expired label `{args.label}` after {args.hours}h to reduce bypass drift. "
                "If bypass is still required, re-apply label with a fresh justification."
            )
        }
        comment_url = f"{API_BASE}/repos/{owner}/{repo}/issues/{number}/comments"
        github_request(token, "POST", comment_url, comment_body)

    print(f"Checked {len(issues)} labeled items. Expired: {expired}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
