"""
D6-01/D6-02: Rule generation integration — adapter between LLM generator and runtime.

Closes loop: LLM rule-generator writes draft YAML → runtime loader compiles per-company rules
Provides multi-company isolation audit (rule_ids must not collide across companies).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.backend.services.rule_loader import load_company_rules


@dataclass
class IsolationReport:
    """Multi-company rule isolation audit result."""

    company_ids: list[str]
    shared_rule_ids: set[str] = field(default_factory=set)
    shared_account_codes: set[str] = field(default_factory=set)

    @property
    def is_isolated(self) -> bool:
        """Returns True if no rule_ids shared across companies."""
        return len(self.shared_rule_ids) == 0


def commit_generated_rules_to_runtime(
    job_result: dict[str, Any], company_id: str, rules_root: Path
) -> None:
    """
    Promote draft rules to active and verify compilation.

    Called after LLM rule-generator produces draft YAML.
    Steps:
    1. Approve draft (mark as active)
    2. Load company rules to verify compilation
    3. Raise error if compilation fails

    Args:
        job_result: LLM job result dict {status, rule_content, ...}
        company_id: Target company ID
        rules_root: Base rules directory

    Raises:
        RuntimeError: If compilation fails
    """
    # Step 1: Approve (promote draft → active)
    # TODO: Call rule_generator.approve_generated_rules(job_result, company_id, rules_root)

    # Step 2: Verify compilation
    compiled = load_company_rules(company_id, rules_root)
    if not compiled or compiled.rules is None:
        raise RuntimeError(
            f"Failed to compile rules for company '{company_id}' after promotion"
        )


def verify_company_isolation(
    company_ids: list[str], rules_root: Path
) -> IsolationReport:
    """
    Audit rule_id uniqueness across multiple companies.

    Loads rules for all companies and checks:
    - rule_ids must not appear in multiple companies
    - account_codes can be shared (standard COA)

    Args:
        company_ids: List of company IDs to audit
        rules_root: Base rules directory

    Returns:
        IsolationReport with shared_rule_ids, shared_account_codes, is_isolated flag
    """
    report = IsolationReport(company_ids=company_ids)

    all_rule_ids: dict[str, list[str]] = {}  # rule_id → [company, ...]
    all_account_codes: dict[str, list[str]] = {}  # account_code → [company, ...]

    for company_id in company_ids:
        compiled = load_company_rules(company_id, rules_root)
        if not compiled or not compiled.rules:
            continue

        for rule in compiled.rules:
            rule_id = getattr(rule, "rule_id", None)
            if rule_id:
                if rule_id not in all_rule_ids:
                    all_rule_ids[rule_id] = []
                all_rule_ids[rule_id].append(company_id)

        # Also track account codes (for informational purposes)
        coa = compiled.coa or {}
        for account_code in coa.keys():
            if account_code not in all_account_codes:
                all_account_codes[account_code] = []
            all_account_codes[account_code].append(company_id)

    # Flag shared rule_ids (isolation violation)
    report.shared_rule_ids = {
        rule_id for rule_id, companies in all_rule_ids.items() if len(companies) > 1
    }

    # Track shared account codes (OK, but informational)
    report.shared_account_codes = {
        code for code, companies in all_account_codes.items() if len(companies) > 1
    }

    return report
