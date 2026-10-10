from datetime import datetime

import pytest

from townhall.issues import TroubleshootingIssue
from townhall.period import KST
from townhall.renderer import NO_ISSUE_TEXT, render_townhall_body
from townhall.summarizer import (
    DIFFICULTY_HEADING,
    LESSON_HEADING,
    LINK_HEADING,
    MISSING_RETROSPECTIVE_LINE,
    normalize_summary_text,
    RESOLUTION_HEADING,
    summarize_issue,
    summarize_issue_safely,
    validate_summary_format,
)

BODY_WITH_RETROSPECTIVE = """# 2026-10-05 배포 실패

## 🐞 에러 내용
- 배포가 실패함. 토큰 ghp_""" + "a" * 36 + """ 이 로그에 노출됨

## 🔍 원인 분석
- 환경 변수 누락

## ✅ 해결 방법
- 변수를 추가함

## 회고
- 배포 전 체크리스트가 필요함
"""

BODY_WITHOUT_RETROSPECTIVE = BODY_WITH_RETROSPECTIVE.split("## 회고")[0]

VALID_SUMMARY = f"""{DIFFICULTY_HEADING}
- 배포 실패 (원인: 환경 변수 누락)

{RESOLUTION_HEADING}
- 변수를 추가함

{LESSON_HEADING}
- 체크리스트 필요
"""


def make_issue(body):
    return TroubleshootingIssue(
        number=3,
        title="[Troubleshooting] 배포 실패",
        author="whale5500d",
        created_at=datetime(2026, 10, 5, tzinfo=KST),
        state="OPEN",
        url="https://github.com/100-hours-a-week/KTB4-20th-wiki/issues/3",
        body=body,
    )


class RecordingTextGenerator:
    def __init__(self, response_text):
        self.response_text = response_text
        self.received_prompt = None

    def __call__(self, prompt):
        self.received_prompt = prompt
        return self.response_text


def test_validate_accepts_valid_summary():
    validate_summary_format(VALID_SUMMARY)


@pytest.mark.parametrize(
    "broken_summary",
    [
        "형식과 무관한 응답",
        VALID_SUMMARY.replace(LESSON_HEADING, ""),
        f"서문입니다\n{VALID_SUMMARY}",
        f"{RESOLUTION_HEADING}\n- a\n\n{DIFFICULTY_HEADING}\n- b\n\n{LESSON_HEADING}\n- c",
        f"{DIFFICULTY_HEADING}\n- a\n\n{RESOLUTION_HEADING}\n\n{LESSON_HEADING}\n- c",
    ],
)
def test_validate_rejects_broken_summary(broken_summary):
    with pytest.raises(ValueError):
        validate_summary_format(broken_summary)


def test_summarize_issue_builds_item_with_title_summary_and_link():
    item = summarize_issue(make_issue(BODY_WITH_RETROSPECTIVE), RecordingTextGenerator(VALID_SUMMARY))

    assert item.startswith("### 배포 실패\n")
    assert "[Troubleshooting]" not in item
    assert "- 체크리스트 필요" in item
    assert f"{LINK_HEADING}\n- https://github.com/100-hours-a-week/KTB4-20th-wiki/issues/3" in item


def test_prompt_contains_redacted_body_without_secret():
    generator = RecordingTextGenerator(VALID_SUMMARY)
    summarize_issue(make_issue(BODY_WITH_RETROSPECTIVE), generator)

    assert "ghp_" not in generator.received_prompt
    assert "[REDACTED]" in generator.received_prompt


def test_missing_retrospective_forces_marker_even_if_model_invents_lesson():
    item = summarize_issue(make_issue(BODY_WITHOUT_RETROSPECTIVE), RecordingTextGenerator(VALID_SUMMARY))

    assert "체크리스트 필요" not in item
    assert f"{LESSON_HEADING}\n{MISSING_RETROSPECTIVE_LINE}" in item


def test_secret_in_model_output_is_masked():
    leaking_summary = VALID_SUMMARY.replace("변수를 추가함", "키 AKIAABCDEFGHIJKLMNOP 교체")
    item = summarize_issue(make_issue(BODY_WITH_RETROSPECTIVE), RecordingTextGenerator(leaking_summary))
    assert "AKIAABCDEFGHIJKLMNOP" not in item


def test_safe_summary_returns_placeholder_on_format_violation():
    outcome = summarize_issue_safely(make_issue(BODY_WITH_RETROSPECTIVE), RecordingTextGenerator("엉뚱한 응답"))

    assert outcome.succeeded is False
    assert outcome.item_text == "### 배포 실패\n\n(요약 실패: https://github.com/100-hours-a-week/KTB4-20th-wiki/issues/3)"


def test_safe_summary_returns_placeholder_on_generator_error():
    def failing_generator(prompt):
        raise RuntimeError("API 오류")

    outcome = summarize_issue_safely(make_issue(BODY_WITH_RETROSPECTIVE), failing_generator)
    assert outcome.succeeded is False
    assert "(요약 실패:" in outcome.item_text


def test_safe_summary_reports_success():
    outcome = summarize_issue_safely(make_issue(BODY_WITH_RETROSPECTIVE), RecordingTextGenerator(VALID_SUMMARY))
    assert outcome.succeeded is True


def test_render_body_orders_courses_and_fills_empty_ones():
    body = render_townhall_body({"AI": ["### a"], "풀스택": ["### f1", "### f2"]})

    assert body.index("## 풀스택") < body.index("## AI") < body.index("## 클라우드")
    assert "### f1\n\n### f2" in body
    assert f"## 클라우드\n\n{NO_ISSUE_TEXT}" in body
    assert "## 미분류" not in body


def test_render_body_includes_unclassified_only_when_present():
    body = render_townhall_body({"미분류": ["### u"]})
    assert body.index("## 클라우드") < body.index("## 미분류")
    assert "### u" in body


def test_normalize_collapses_repeated_bullet_markers_and_trailing_periods():
    messy_summary = VALID_SUMMARY.replace("- 배포 실패 (원인: 환경 변수 누락)", "- - 원인: 환경 변수 누락.")
    normalized = normalize_summary_text(messy_summary)

    assert "- - " not in normalized
    assert "- 원인: 환경 변수 누락\n" in normalized + "\n"
    assert "- 변수를 추가함" in normalized


def test_normalize_keeps_periods_inside_sentences_and_marker_line():
    text = f"{LESSON_HEADING}\n{MISSING_RETROSPECTIVE_LINE}\n- v1.2 적용. 이후 확인함."
    normalized = normalize_summary_text(text)

    assert MISSING_RETROSPECTIVE_LINE in normalized
    assert "- v1.2 적용. 이후 확인함" in normalized
    assert not normalized.endswith(".")


def test_summarize_issue_applies_normalization_before_validation():
    messy_summary = VALID_SUMMARY.replace("- 변수를 추가함", "- - 변수를 추가함.")
    item = summarize_issue(make_issue(BODY_WITH_RETROSPECTIVE), RecordingTextGenerator(messy_summary))
    assert "- - " not in item
    assert "- 변수를 추가함\n" in item
