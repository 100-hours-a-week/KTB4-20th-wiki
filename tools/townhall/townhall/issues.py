"""트러블슈팅 이슈의 데이터 모델, 집계 기간 필터, 본문 섹션 추출을 담당하는 모듈."""

import re
from dataclasses import dataclass
from datetime import datetime

from townhall.period import CollectionPeriod

TROUBLESHOOTING_TITLE_PREFIX = "[Troubleshooting]"

# 템플릿 제목(에러 내용/해결 방법) 외에 실제 이슈에서 쓰이는 변형(문제 상황/결정 및 대응)도 인식함.
# 앞쪽 항목이 우선하므로 '문제 해결'처럼 겹치는 제목은 해결 섹션으로 분류됨.
SECTION_KEYWORDS = (
    ("retrospective", ("회고",)),
    ("cause", ("원인",)),
    ("solution", ("해결", "대응")),
    ("error", ("에러", "문제")),
)
TEMPLATE_PLACEHOLDER_PATTERN = re.compile(r"^[-*\s_]*\(내용 작성\)[_\s]*$")
TITLE_DATE_PREFIX_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\([월화수목금토일]\))?\s*")


@dataclass(frozen=True)
class TroubleshootingIssue:
    number: int
    title: str
    author: str
    created_at: datetime
    state: str
    url: str
    body: str


@dataclass(frozen=True)
class IssueSections:
    error: str
    cause: str
    solution: str
    retrospective: str


def is_troubleshooting_title(title: str) -> bool:
    return title.strip().startswith(TROUBLESHOOTING_TITLE_PREFIX)


def strip_title_prefix(title: str) -> str:
    """'[Troubleshooting] 2026-09-26(토) 제목'에서 접두어와 앞쪽 날짜를 제외한 제목을 반환함."""
    stripped_title = title.strip()
    if stripped_title.startswith(TROUBLESHOOTING_TITLE_PREFIX):
        stripped_title = stripped_title[len(TROUBLESHOOTING_TITLE_PREFIX) :].strip()
    return TITLE_DATE_PREFIX_PATTERN.sub("", stripped_title)


def parse_issue_from_github_json(raw_issue: dict) -> TroubleshootingIssue:
    """gh CLI의 JSON 한 건을 TroubleshootingIssue로 변환함. 작성자가 삭제된 계정이면 빈 문자열임."""
    author_info = raw_issue.get("author") or {}
    return TroubleshootingIssue(
        number=raw_issue["number"],
        title=raw_issue["title"],
        author=author_info.get("login", ""),
        created_at=datetime.fromisoformat(raw_issue["createdAt"].replace("Z", "+00:00")),
        state=raw_issue.get("state", ""),
        url=raw_issue["url"],
        body=raw_issue.get("body") or "",
    )


def select_issues_in_period(
    issues: list[TroubleshootingIssue], period: CollectionPeriod
) -> list[TroubleshootingIssue]:
    """제목 접두어와 생성 시각(start 이상, end 미만)을 만족하는 이슈를 생성 순으로 반환함."""
    selected_issues = [
        issue
        for issue in issues
        if is_troubleshooting_title(issue.title) and period.start <= issue.created_at < period.end
    ]
    return sorted(selected_issues, key=lambda issue: issue.created_at)


def _classify_heading(heading_line: str) -> str | None:
    for section_name, keywords in SECTION_KEYWORDS:
        if any(keyword in heading_line for keyword in keywords):
            return section_name
    return None


def _clean_section_text(section_lines: list[str]) -> str:
    kept_lines = [line for line in section_lines if not TEMPLATE_PLACEHOLDER_PATTERN.match(line)]
    cleaned_text = "\n".join(kept_lines).strip()
    # '-'처럼 bullet 기호만 남은 섹션은 내용이 없는 것으로 봄.
    return cleaned_text if re.search(r"\w", cleaned_text) else ""


def extract_sections(issue_body: str) -> IssueSections:
    """'## ' 제목의 키워드(에러·문제/원인/해결·대응/회고)로 본문 섹션을 나눔. 양식 자리표시자는 빈 섹션으로 봄."""
    collected_lines: dict[str, list[str]] = {name: [] for name, _ in SECTION_KEYWORDS}
    current_section: str | None = None
    for line in issue_body.splitlines():
        if line.startswith("## "):
            current_section = _classify_heading(line)
        elif current_section is not None:
            collected_lines[current_section].append(line)
    return IssueSections(
        error=_clean_section_text(collected_lines["error"]),
        cause=_clean_section_text(collected_lines["cause"]),
        solution=_clean_section_text(collected_lines["solution"]),
        retrospective=_clean_section_text(collected_lines["retrospective"]),
    )
