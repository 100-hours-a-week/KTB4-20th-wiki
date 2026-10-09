"""트러블슈팅 이슈 한 건을 타운홀 양식(어려움/해결/배운 점/링크)의 markdown 항목으로 요약하는 모듈."""

import re
from dataclasses import dataclass
from typing import Callable

from townhall.issues import (
    IssueSections,
    TroubleshootingIssue,
    extract_sections,
    strip_title_prefix,
)
from townhall.redaction import redact_sensitive_text

TextGenerator = Callable[[str], str]

DIFFICULTY_HEADING = "**1. 어떤 어려움이 있었나**"
RESOLUTION_HEADING = "**2. 어떻게 해결 중인가 또는 해결했는가**"
LESSON_HEADING = "**3. 배운 점**"
LINK_HEADING = "**4. 트러블슈팅 링크**"
SUMMARY_HEADINGS = (DIFFICULTY_HEADING, RESOLUTION_HEADING, LESSON_HEADING)

MISSING_RETROSPECTIVE_LINE = "- (작성 필요: 회고 없음)"
NO_CONTENT_TEXT = "(내용 없음)"

REPEATED_BULLET_PATTERN = re.compile(r"^(\s*)(?:-\s+){2,}")
TRAILING_PERIOD_PATTERN = re.compile(r"[.。]+\s*$")


def build_prompt(sections: IssueSections) -> str:
    """요약 지시문, 출력 양식, 이슈 본문 섹션을 하나의 prompt로 합침."""
    retrospective_text = sections.retrospective or "(회고 없음)"
    return f"""아래 트러블슈팅 이슈를 타운홀 미팅 발표 보조용 요약본으로 작성한다.

[핵심 메시지]
다른 팀 청중이 문제 상황, 대응 방향, 배운 점을 한눈에 파악하게 한다. 발표에서 말로 보충하므로 간결하게 쓴다.

[규칙]
1. 입력에 없는 원인, 해결책, 인사이트는 절대 추가하지 않는다.
2. 항목 1에는 '에러 내용'을 요약하고, 마지막 bullet 하나를 "- 원인: ..."으로 시작해 '원인 분석'을 한 줄로 압축한다. 항목 1은 원인 bullet을 포함해 최대 3개다.
3. 항목 2에는 '해결 방법'의 핵심 조치만 최대 3개 bullet로 요약한다. 같은 내용을 반복하지 않는다. 해결 중인지 해결했는지는 입력의 시제를 그대로 따른다.
4. 항목 3은 '회고'에서만 가져와 최대 2개 bullet로 요약한다. 회고가 "(회고 없음)"이면 "{MISSING_RETROSPECTIVE_LINE}" 한 줄만 쓴다.
5. 약어는 풀어 쓰지 않고 입력의 표현을 그대로 쓴다.
6. 특정 사람의 이름이나 계정을 지목한 비난성 표현은 쓰지 않고, 필요하면 "담당자", "팀"처럼 중립적으로 바꾼다.
7. 각 bullet은 한 문장, 가능하면 60자 안팎으로 쓴다. 명령어, 쿼리, 설정값 같은 세부 사항은 생략한다.
8. 모든 bullet은 개조식 어미(~함, ~임, ~됨)로 끝내고, 입력이 존댓말이나 평서문이어도 이 문체로 통일한다. 문장 끝에 마침표는 붙이지 않는다.
9. 가능한 한 입력의 표현과 용어를 그대로 쓰고, 새로운 단어로 바꿔 쓰지 않는다.
10. 제목, 서문, 코드 블록 표시 없이 아래 출력 양식의 markdown만 출력한다. 링크 항목은 쓰지 않는다.

[출력 양식]
{DIFFICULTY_HEADING}
- ...

{RESOLUTION_HEADING}
- ...

{LESSON_HEADING}
- ...

[에러 내용]
{sections.error or NO_CONTENT_TEXT}

[원인 분석]
{sections.cause or NO_CONTENT_TEXT}

[해결 방법]
{sections.solution or NO_CONTENT_TEXT}

[회고]
{retrospective_text}
"""


def validate_summary_format(summary_text: str) -> None:
    """요약이 세 제목을 순서대로 갖고, 각 제목 아래에 bullet이 하나 이상 있는지 검증함."""
    stripped_lines = [line.strip() for line in summary_text.strip().splitlines()]
    heading_indexes = []
    for heading in SUMMARY_HEADINGS:
        if heading not in stripped_lines:
            raise ValueError(f"'{heading}' 제목이 없음.")
        heading_indexes.append(stripped_lines.index(heading))
    if heading_indexes != sorted(heading_indexes) or heading_indexes[0] != 0:
        raise ValueError("제목 순서가 맞지 않거나 첫 줄이 항목 1 제목이 아님.")
    section_ends = heading_indexes[1:] + [len(stripped_lines)]
    for heading, start_index, end_index in zip(SUMMARY_HEADINGS, heading_indexes, section_ends):
        section_lines = stripped_lines[start_index + 1 : end_index]
        if not any(line.startswith("- ") for line in section_lines):
            raise ValueError(f"'{heading}' 아래에 bullet이 없음.")


def normalize_summary_text(summary_text: str) -> str:
    """모델이 자주 어기는 서식을 코드로 정리함: 중복 bullet 기호('- - ')를 하나로 합치고, bullet 끝 마침표를 제거함."""
    normalized_lines = []
    for line in summary_text.strip().splitlines():
        line = REPEATED_BULLET_PATTERN.sub(r"\1- ", line)
        if line.lstrip().startswith("- "):
            line = TRAILING_PERIOD_PATTERN.sub("", line)
        normalized_lines.append(line.rstrip())
    return "\n".join(normalized_lines)


def _replace_lesson_with_missing_marker(summary_text: str) -> str:
    """배운 점은 마지막 항목이므로, 제목 이후를 회고 없음 표시로 교체함."""
    summary_lines = summary_text.strip().splitlines()
    lesson_heading_index = [line.strip() for line in summary_lines].index(LESSON_HEADING)
    return "\n".join(summary_lines[: lesson_heading_index + 1] + [MISSING_RETROSPECTIVE_LINE])


def summarize_issue(issue: TroubleshootingIssue, generate_text: TextGenerator) -> str:
    """이슈 한 건을 '### 제목' + 1~3 요약 + 4 링크의 markdown 항목으로 만듦. 실패하면 예외를 냄."""
    redacted_body = redact_sensitive_text(issue.body).text
    sections = extract_sections(redacted_body)
    summary_text = generate_text(build_prompt(sections)).strip()
    summary_text = normalize_summary_text(summary_text)
    validate_summary_format(summary_text)
    if not sections.retrospective:
        summary_text = _replace_lesson_with_missing_marker(summary_text)
    return render_issue_item(issue, summary_text)


def render_issue_item(issue: TroubleshootingIssue, summary_text: str) -> str:
    item_title = redact_sensitive_text(strip_title_prefix(issue.title)).text
    redacted_summary = redact_sensitive_text(summary_text).text
    return f"### {item_title}\n\n{redacted_summary}\n\n{LINK_HEADING}\n- {issue.url}"


def render_failed_item(issue: TroubleshootingIssue) -> str:
    item_title = redact_sensitive_text(strip_title_prefix(issue.title)).text
    return f"### {item_title}\n\n(요약 실패: {issue.url})"


@dataclass(frozen=True)
class SummaryOutcome:
    item_text: str
    succeeded: bool


def summarize_issue_safely(issue: TroubleshootingIssue, generate_text: TextGenerator) -> SummaryOutcome:
    """요약 실패(LLM 오류, 양식 위반)가 전체를 멈추지 않도록 자리표시자 항목으로 대체함."""
    try:
        return SummaryOutcome(summarize_issue(issue, generate_text), succeeded=True)
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 해당 이슈만 자리표시자로 대체함.
        print(f"[경고] #{issue.number} 요약 실패: {error}")
        return SummaryOutcome(render_failed_item(issue), succeeded=False)
