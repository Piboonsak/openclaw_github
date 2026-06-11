"""
D3-03: Persistent cache for Map Review account mapping decisions.

Stores confirmed vendor → account mappings to short-circuit resolver
on subsequent documents with same vendor + document_type.

Cache format:
{
    "schema_version": 1,
    "entries": {
        "<signature>": {
            "account_code": "1110",
            "account_name": "Accounts Receivable",
            "source": "map_review",
            "updated_at": "2026-06-10T14:00:00Z",
            "hit_count": 3
        },
        ...
    }
}

Signature format: "<source_text_normalized>|<document_type>"
  - source_text_normalized: seller_name or vendor_name or source_text, stripped and lowercased
  - document_type: e.g., "Purchase Order", "Invoice"
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class CacheEntry:
    """Single cache entry for a vendor+doc_type signature."""

    def __init__(
        self,
        account_code: str,
        account_name: str,
        source: str = "map_review",
        updated_at: Optional[str] = None,
        hit_count: int = 0,
    ):
        self.account_code = account_code
        self.account_name = account_name
        self.source = source
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()
        self.hit_count = hit_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "source": self.source,
            "updated_at": self.updated_at,
            "hit_count": self.hit_count,
        }


def make_signature(source_text: str, document_type: str) -> str:
    """
    Generate cache signature from vendor identifier + document type.

    Args:
        source_text: Seller/vendor name or document text snippet
        document_type: E.g., "Purchase Order", "Invoice"

    Returns:
        Signature string: "<normalized_text>|<doc_type>"
    """
    if not source_text or not document_type:
        raise ValueError("source_text and document_type required")
    normalized = source_text.strip().lower()
    return f"{normalized}|{document_type}"


def cache_path_for(rules_root: Path, company_id: str) -> Path:
    """
    Resolve cache file path for a company.

    Cache stored alongside rule_coa.yaml at: rules/{company_id}/resolver_cache.json

    Args:
        rules_root: Base rules directory (e.g., ./rules)
        company_id: Company identifier

    Returns:
        Path to resolver_cache.json
    """
    return rules_root / company_id / "resolver_cache.json"


def load_cache(cache_path: Path) -> dict[str, Any]:
    """
    Load cache from disk, or return empty schema if file missing.

    Args:
        cache_path: Path to resolver_cache.json

    Returns:
        Cache dict with schema_version and entries
    """
    if not cache_path.exists():
        return {"schema_version": 1, "entries": {}}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"schema_version": 1, "entries": {}}


def lookup(
    rules_root: Path, company_id: str, signature: str
) -> Optional[dict[str, Any]]:
    """
    Lookup a cached account mapping by signature.

    Args:
        rules_root: Base rules directory
        company_id: Company identifier
        signature: Vendor+doc_type signature from make_signature()

    Returns:
        Cache entry dict {account_code, account_name, ...} or None if miss
    """
    cache_path = cache_path_for(rules_root, company_id)
    cache = load_cache(cache_path)
    return cache.get("entries", {}).get(signature)


def write_back(
    rules_root: Path,
    company_id: str,
    signature: str,
    account_code: str,
    account_name: str,
    source: str = "map_review",
) -> None:
    """
    Persist a confirmed account mapping to cache.

    Called by apply_map_review() after human confirms an account pick.
    Auto-increments hit_count for existing signatures, or creates new entry.

    Args:
        rules_root: Base rules directory
        company_id: Company identifier
        signature: Vendor+doc_type signature
        account_code: Account code (e.g., "1110")
        account_name: Account name (e.g., "Accounts Receivable")
        source: Source indicator (default: "map_review")
    """
    cache_path = cache_path_for(rules_root, company_id)
    cache = load_cache(cache_path)

    entries = cache.get("entries", {})
    if signature in entries:
        entries[signature]["hit_count"] = entries[signature].get("hit_count", 0) + 1
        entries[signature]["updated_at"] = datetime.now(timezone.utc).isoformat()
    else:
        entries[signature] = {
            "account_code": account_code,
            "account_name": account_name,
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "hit_count": 1,
        }

    cache["entries"] = entries
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
