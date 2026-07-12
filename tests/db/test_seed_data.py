from __future__ import annotations

import uuid
from types import SimpleNamespace

from scripts.seed_data import (
    DEFAULT_COMPANIES_PATH,
    DEFAULT_INCLUDED_PAGE_CREDITS,
    DEFAULT_PLAN_NAME,
    DEFAULT_PRICE_EFFECTIVE_THB,
    DEFAULT_PRICE_ORIGINAL_THB,
    _get_or_create_admin_user,
    build_credit_plan_seed,
    build_master_templates,
    get_required_env,
    hash_password,
    load_company_seeds,
    verify_password,
)


class _FakeSeedSession:
    """Minimal session stand-in for exercising the pure create branch of
    `_get_or_create_admin_user` without a live database."""

    def __init__(self) -> None:
        self.added: list[object] = []

    def execute(self, _stmt):  # noqa: ANN001
        class _Result:
            def scalar_one_or_none(self):  # noqa: ANN001
                return None

        return _Result()

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)

    def flush(self) -> None:
        return None


def test_load_company_seeds_reads_companies_json() -> None:
    companies = load_company_seeds(DEFAULT_COMPANIES_PATH)

    assert len(companies) >= 3
    assert all(company["tax_id"].isdigit() for company in companies)
    assert all(company["branch_code"] for company in companies)


def test_build_master_templates_matches_task_802_contract() -> None:
    templates = build_master_templates()
    by_name = {template["template_name"]: template for template in templates}

    assert len(templates) == 2
    assert len(by_name["Express GL"]["columns"]) == 8
    assert len(by_name["Purchase Tax"]["columns"]) == 12
    assert by_name["Express GL"]["file_format"] == "csv"
    assert by_name["Purchase Tax"]["file_format"] == "xlsx"


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


def test_get_required_env_raises_for_missing_values(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    try:
        get_required_env("ADMIN_PASSWORD")
    except RuntimeError as exc:
        assert "ADMIN_PASSWORD" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when env var is missing")


def test_bootstrap_admin_user_is_seeded_as_true_sys_admin() -> None:
    """HR-07-03: the single bootstrap operator account must be seeded as a real
    `sys_admin`, not `admin` — otherwise the reviewer's "System Admin" path is a
    display label only and (correctly) cannot see the company delete action or
    save sys_admin company assignments."""
    session = _FakeSeedSession()
    tenant = SimpleNamespace(id=uuid.uuid4())

    user, created = _get_or_create_admin_user(
        session,
        tenant,
        email="ops@bwc.co.th",
        username="ops",
        display_name="System Admin",
        password="ChangeMe123!",
    )

    assert created is True
    assert user.role == "sys_admin"

