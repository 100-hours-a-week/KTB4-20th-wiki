import pytest

from townhall.redaction import REDACTED, redact_sensitive_text

SECRET_SAMPLES = [
    "ghp_" + "a" * 36,
    "github_pat_" + "A1b2C3d4E5" * 3,
    "sk-" + "x" * 30,
    "AKIA" + "ABCDEFGHIJKLMNOP",
    "AIza" + "S" * 35,
    "xoxb-1234567890-abcdefghij",
    "eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4",
    "Bearer abcdefghijklmnopqrstuvwxyz012345",
]


@pytest.mark.parametrize("secret_text", SECRET_SAMPLES)
def test_token_patterns_are_redacted(secret_text):
    result = redact_sensitive_text(f"로그에 {secret_text} 가 찍혔다.")
    assert secret_text not in result.text
    assert REDACTED in result.text
    assert result.redacted_kinds


def test_key_value_keeps_key_and_masks_value():
    result = redact_sensitive_text("DB password=hunter2 로 접속함")
    assert "hunter2" not in result.text
    assert f"password={REDACTED}" in result.text


def test_key_value_not_double_counted_when_already_redacted():
    result = redact_sensitive_text("token: " + "ghp_" + "a" * 36)
    assert result.text.count(REDACTED) == 1


def test_email_ip_and_internal_hosts_are_redacted():
    text = "admin@example.com 이 10.0.3.15 와 db.prod.internal, localhost:8080 에 접속함"
    result = redact_sensitive_text(text)
    for leaked in ("admin@example.com", "10.0.3.15", "db.prod.internal", "localhost"):
        assert leaked not in result.text
    assert set(result.redacted_kinds) >= {"email", "ip_address", "internal_host"}


def test_url_credentials_are_redacted():
    result = redact_sensitive_text("clone https://user:pass123@github.com/org/repo.git")
    assert "pass123" not in result.text
    assert "github.com/org/repo.git" in result.text


def test_private_key_block_is_redacted():
    block = "-----BEGIN RSA PRIVATE KEY-----\nabc\ndef\n-----END RSA PRIVATE KEY-----"
    result = redact_sensitive_text(f"키: {block}")
    assert "abc" not in result.text
    assert "private_key" in result.redacted_kinds


def test_allowed_github_links_and_plain_text_are_untouched():
    text = "원본: https://github.com/100-hours-a-week/KTB4-20th-wiki/issues/12 버전 1.2.3 참고"
    result = redact_sensitive_text(text)
    assert result.text == text
    assert result.redacted_kinds == ()


def test_invalid_ipv4_like_version_is_untouched():
    result = redact_sensitive_text("라이브러리 버전 999.1.2.3 사용")
    assert result.text == "라이브러리 버전 999.1.2.3 사용"
    assert "ip_address" not in result.redacted_kinds
