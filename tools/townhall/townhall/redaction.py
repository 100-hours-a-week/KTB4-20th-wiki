"""LLM에 넘기기 전과 게시 전에 키/토큰, 계정 정보, 내부 주소를 [REDACTED]로 치환하는 모듈.

github.com/100-hours-a-week/* 링크와 일반 공개 URL은 건드리지 않음.
"""

import re
from dataclasses import dataclass
from typing import Callable

REDACTED = "[REDACTED]"

PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL
)
URL_CREDENTIAL_PATTERN = re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)")
KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b(\s*[:=]\s*)(\S+)"
)
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
INTERNAL_HOST_PATTERN = re.compile(
    r"\blocalhost\b|\b[\w-]+(?:\.[\w-]+)*\.(?:internal|local|corp|lan)\b", re.IGNORECASE
)

TOKEN_PATTERNS = (
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("api_key", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,})\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")),
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redacted_kinds: tuple[str, ...]


def _is_valid_ipv4(candidate: str) -> bool:
    return all(0 <= int(octet) <= 255 for octet in candidate.split("."))


def redact_sensitive_text(text: str) -> RedactionResult:
    """민감 패턴을 [REDACTED]로 치환한 텍스트와, 치환된 종류 목록을 반환함."""
    found_kinds: list[str] = []

    def replace_all(kind: str, pattern: re.Pattern, replacement: str | Callable) -> None:
        nonlocal text
        replaced_text = pattern.sub(replacement, text)
        if replaced_text != text:
            found_kinds.append(kind)
            text = replaced_text

    def mask_key_value(match: re.Match) -> str:
        if match.group(3).startswith(REDACTED):
            return match.group(0)
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    def mask_ipv4(match: re.Match) -> str:
        return REDACTED if _is_valid_ipv4(match.group(0)) else match.group(0)

    replace_all("private_key", PRIVATE_KEY_BLOCK_PATTERN, REDACTED)
    replace_all("url_credential", URL_CREDENTIAL_PATTERN, REDACTED)
    for kind, pattern in TOKEN_PATTERNS:
        replace_all(kind, pattern, REDACTED)
    replace_all("key_value", KEY_VALUE_PATTERN, mask_key_value)
    replace_all("email", EMAIL_PATTERN, REDACTED)
    replace_all("ip_address", IPV4_PATTERN, mask_ipv4)
    replace_all("internal_host", INTERNAL_HOST_PATTERN, REDACTED)

    return RedactionResult(text=text, redacted_kinds=tuple(dict.fromkeys(found_kinds)))
