"""Tests for canonical SecureMCP principal identity resolution."""

from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.security.principal import principal_id_from_access_token


def _token(value: str, **kwargs) -> AccessToken:
    return AccessToken(token=value, client_id="client", scopes=[], **kwargs)


def test_jwts_with_shared_header_have_distinct_principal_ids():
    first = _token("eyJhbGci.payload-one.signature-one")
    second = _token("eyJhbGci.payload-two.signature-two")

    assert principal_id_from_access_token(first) != principal_id_from_access_token(
        second
    )


def test_token_rotation_preserves_issuer_subject_principal_id():
    first = _token(
        "old-token",
        subject="user-1",
        claims={"iss": "https://issuer.example", "sub": "user-1"},
    )
    second = _token(
        "new-token",
        subject="user-1",
        claims={"iss": "https://issuer.example", "sub": "user-1"},
    )

    assert principal_id_from_access_token(first) == principal_id_from_access_token(
        second
    )


def test_same_subject_from_different_issuers_has_distinct_principal_ids():
    first = _token("one", subject="user-1", claims={"iss": "issuer-a"})
    second = _token("two", subject="user-1", claims={"iss": "issuer-b"})

    assert principal_id_from_access_token(first) != principal_id_from_access_token(
        second
    )


def test_principal_id_does_not_contain_token_or_subject():
    token = _token("top-secret-token", subject="private-user")

    principal = principal_id_from_access_token(token)

    assert principal is not None
    assert principal.startswith("principal:")
    assert "top-secret-token" not in principal
    assert "private-user" not in principal
