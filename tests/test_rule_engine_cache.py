"""D3-03: Tests for F-loop mapping cache write-back in rule_engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.backend.services.rule_engine import (
    _make_mapping_cache_key,
    _read_mapping_cache,
    _write_mapping_cache,
    on_map_review_confirmed,
    resolve_variable_account,
)


class TestMappingCacheKey:
    """_make_mapping_cache_key() — stable, normalised key generation."""

    def test_same_input_produces_same_key(self):
        k1 = _make_mapping_cache_key("บริษัท ABC", "ค่าไฟ")
        k2 = _make_mapping_cache_key("บริษัท ABC", "ค่าไฟ")
        assert k1 == k2

    def test_case_normalisation(self):
        assert _make_mapping_cache_key("Vendor A", "Desc") == _make_mapping_cache_key("vendor a", "desc")

    def test_whitespace_normalisation(self):
        assert _make_mapping_cache_key("  Vendor  ", "  D  ") == _make_mapping_cache_key("Vendor", "D")

    def test_different_inputs_produce_different_keys(self):
        k1 = _make_mapping_cache_key("Vendor A", "ค่าเช่า")
        k2 = _make_mapping_cache_key("Vendor A", "ค่าไฟ")
        assert k1 != k2


class TestReadWriteMappingCache:
    """_read_mapping_cache / _write_mapping_cache — JSON persistence."""

    def test_write_then_read_returns_entry(self, tmp_path):
        key = "abc123"
        _write_mapping_cache("COMP1", key, "5040", "Electricity Expense", "map_review", tmp_path)
        result = _read_mapping_cache("COMP1", key, tmp_path)
        assert result is not None
        assert result["account_code"] == "5040"
        assert result["account_name"] == "Electricity Expense"
        assert result["source"] == "map_review"

    def test_read_missing_key_returns_none(self, tmp_path):
        assert _read_mapping_cache("COMP1", "no_such_key", tmp_path) is None

    def test_read_missing_company_returns_none(self, tmp_path):
        assert _read_mapping_cache("NO_COMPANY", "key", tmp_path) is None

    def test_update_overwrites_existing_entry(self, tmp_path):
        key = "abc123"
        _write_mapping_cache("COMP1", key, "5040", "Old Name", "map_review", tmp_path)
        _write_mapping_cache("COMP1", key, "5045", "Rent Expense", "map_review", tmp_path)
        result = _read_mapping_cache("COMP1", key, tmp_path)
        assert result["account_code"] == "5045"
        assert result["account_name"] == "Rent Expense"

    def test_different_companies_isolated(self, tmp_path):
        key = _make_mapping_cache_key("Vendor A", "Service")
        _write_mapping_cache("COMP1", key, "5040", "Expense A", "map_review", tmp_path)
        _write_mapping_cache("COMP2", key, "5080", "Expense B", "map_review", tmp_path)
        assert _read_mapping_cache("COMP1", key, tmp_path)["account_code"] == "5040"
        assert _read_mapping_cache("COMP2", key, tmp_path)["account_code"] == "5080"

    def test_cache_file_is_valid_json(self, tmp_path):
        key = "k1"
        _write_mapping_cache("COMP1", key, "5040", "Test", "map_review", tmp_path)
        cache_file = tmp_path / "mapping_cache" / "COMP1.json"
        assert cache_file.exists()
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert key in data


class TestOnMapReviewConfirmed:
    """on_map_review_confirmed() — public F-loop API."""

    def test_returns_cache_key_string(self, tmp_path):
        key = on_map_review_confirmed(
            "COMP1", "บริษัท XYZ", "ค่าไฟฟ้า", "5040", "Electricity Expense",
            cache_root=tmp_path,
        )
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hex

    def test_confirmed_entry_is_retrievable(self, tmp_path):
        on_map_review_confirmed(
            "COMP1", "Vendor A", "Monthly Rent", "5045", "Rent Expense",
            cache_root=tmp_path,
        )
        key = _make_mapping_cache_key("Vendor A", "Monthly Rent")
        result = _read_mapping_cache("COMP1", key, tmp_path)
        assert result["account_code"] == "5045"
        assert result["source"] == "map_review"

    def test_reconfirm_updates_account(self, tmp_path):
        on_map_review_confirmed("COMP1", "Vendor A", "Service", "5040", "", cache_root=tmp_path)
        on_map_review_confirmed("COMP1", "Vendor A", "Service", "5080", "Office Supplies", cache_root=tmp_path)
        key = _make_mapping_cache_key("Vendor A", "Service")
        result = _read_mapping_cache("COMP1", key, tmp_path)
        assert result["account_code"] == "5080"

    def test_account_name_optional(self, tmp_path):
        """on_map_review_confirmed works without account_name."""
        key = on_map_review_confirmed("COMP1", "Vendor B", "Ad spend", "5100", cache_root=tmp_path)
        result = _read_mapping_cache("COMP1", key, tmp_path)
        assert result["account_code"] == "5100"
        assert result["account_name"] == ""


class TestResolveVariableAccountCacheTier:
    """resolve_variable_account() — Tier 1 cache lookup beats Tier 2 keywords."""

    def test_cache_hit_returns_cached_account(self, tmp_path):
        # Write a mapping that overrides the default keyword match
        on_map_review_confirmed("COMP1", "บริษัท XYZ", "ค่าไฟ", "5099", "Custom Account", cache_root=tmp_path)
        context = {
            "company_id": "COMP1",
            "seller_name": "บริษัท XYZ",
            "source_text": "ค่าไฟ",
        }
        result = resolve_variable_account({"account_code": "5xxx"}, context, cache_root=tmp_path)
        assert result["account_code"] == "5099"
        assert result.get("cache_hit") is True

    def test_no_cache_falls_through_to_keyword(self, tmp_path):
        context = {
            "company_id": "COMP1",
            "seller_name": "",
            "source_text": "ค่าไฟฟ้า",
        }
        result = resolve_variable_account({"account_code": "5xxx"}, context, cache_root=tmp_path)
        assert result["account_code"] == "5040"
        assert result.get("cache_hit") is not True

    def test_no_company_id_skips_cache(self, tmp_path):
        """Without company_id, cache is skipped; falls through to keyword."""
        context = {"source_text": "น้ำมัน"}
        result = resolve_variable_account({"account_code": "5xxx"}, context, cache_root=tmp_path)
        assert result["account_code"] == "5020"

    def test_non_variable_account_returned_unchanged(self, tmp_path):
        """Accounts without 'xxx' pass through untouched."""
        context = {"company_id": "COMP1", "source_text": "ค่าไฟ"}
        result = resolve_variable_account({"account_code": "5040", "account_name": "Electricity"}, context, cache_root=tmp_path)
        assert result["account_code"] == "5040"
