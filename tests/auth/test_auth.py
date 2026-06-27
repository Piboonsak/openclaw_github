from __future__ import annotations

import pytest

from src.backend.auth.auth import (
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    password = "SuperSecret123!"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)


def test_access_token_contains_subject_and_type() -> None:
    token = create_access_token("1234", role="admin")
    payload = decode_token(token, expected_type="access")

    assert payload["sub"] == "1234"
    assert payload["type"] == "access"
    assert payload["role"] == "admin"


def test_refresh_token_rejects_wrong_expected_type() -> None:
    token = create_refresh_token("1234")

    with pytest.raises(JWTError):
        decode_token(token, expected_type="access")
