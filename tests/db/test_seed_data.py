from __future__ import annotations

from scripts.seed_data import (
    DEFAULT_COMPANIES_PATH,
    DEFAULT_INCLUDED_PAGE_CREDITS,
    DEFAULT_PLAN_NAME,
    DEFAULT_PRICE_EFFECTIVE_THB,
    DEFAULT_PRICE_ORIGINAL_THB,
    build_credit_plan_seed,
    build_master_templates,
    hash_password,
    load_company_seeds,
    verify_password,
)


def test_load_company_seeds_reads_companies_json() -> None:
    companies = load_company_seeds(DEFAULT_COMPANIES_PATH)

    assert len(companies) >= 3
    assert all(company["tax_id"].isdigit() for company in companies)
    assert all(company["branch_code"] for company in companies)


def test_build_master_templates_matches_task_802_contract() -> None:
    templates = build_master_templates()
    by_name = {template["template_name"]: template for template in templates}

    assert len(templates) == 2
    assert len(by_name["Express GL (Master)"]["columns"]) == 8
    assert len(by_name["Purchase Tax (Master)"]["columns"]) == 12
    assert by_name["Express GL (Master)"]["file_format"] == "csv"
    assert by_name["Purchase Tax (Master)"]["file_format"] == "xlsx"


def test_build_credit_plan_seed_matches_page_credit_dashboard_contract() -> None:
    plan = build_credit_plan_seed()

    assert plan["plan_name"] == DEFAULT_PLAN_NAME
    assert plan["included_page_credits"] == DEFAULT_INCLUDED_PAGE_CREDITS
    assert plan["price_original_thb"] == DEFAULT_PRICE_ORIGINAL_THB
    assert plan["price_effective_thb"] == DEFAULT_PRICE_EFFECTIVE_THB
    assert plan["billing_model"] == "page_credit"


def test_hash_password_is_not_plaintext() -> None:
    password = "ChangeMe123!"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
