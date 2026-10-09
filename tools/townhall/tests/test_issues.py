from datetime import datetime, timezone

from townhall.issues import (
    TroubleshootingIssue,
    extract_sections,
    parse_issue_from_github_json,
    select_issues_in_period,
    strip_title_prefix,
)
from townhall.period import KST, CollectionPeriod
from datetime import date

PERIOD = CollectionPeriod(
    start=datetime(2026, 10, 4, 20, tzinfo=KST),
    end=datetime(2026, 10, 11, 20, tzinfo=KST),
    townhall_date=date(2026, 10, 12),
)

BODY = """# 2026-10-05 배포 실패

## 🐞 에러 내용
- 배포가 실패함

## 🔍 원인 분석
- 환경 변수 누락

## ✅ 해결 방법
- 변수를 추가함

## 회고
- 배포 전 체크리스트가 필요함
"""


def make_issue(created_at, title="[Troubleshooting] 배포 실패", number=1):
    return TroubleshootingIssue(
        number=number,
        title=title,
        author="whale5500d",
        created_at=created_at,
        state="OPEN",
        url=f"https://github.com/o/r/issues/{number}",
        body=BODY,
    )


def test_extract_sections_splits_by_keyword():
    sections = extract_sections(BODY)
    assert sections.error == "- 배포가 실패함"
    assert sections.cause == "- 환경 변수 누락"
    assert sections.solution == "- 변수를 추가함"
    assert sections.retrospective == "- 배포 전 체크리스트가 필요함"


def test_template_placeholder_counts_as_empty():
    body = BODY.replace("- 배포 전 체크리스트가 필요함", "- _(내용 작성)_")
    assert extract_sections(body).retrospective == ""


def test_missing_retrospective_section_is_empty():
    body = BODY.split("## 회고")[0]
    assert extract_sections(body).retrospective == ""


def test_strip_title_prefix():
    assert strip_title_prefix("[Troubleshooting] 배포 실패") == "배포 실패"
    assert strip_title_prefix("배포 실패") == "배포 실패"
    assert strip_title_prefix("[Troubleshooting]  AI·BE 충돌") == "AI·BE 충돌"


def test_strip_title_prefix_removes_leading_date():
    assert strip_title_prefix("[Troubleshooting] 2026-09-26(토) 배포 실패") == "배포 실패"
    assert strip_title_prefix("[Troubleshooting] 2026-09-26 배포 실패") == "배포 실패"
    assert strip_title_prefix("[Troubleshooting] 배포 2026-09-26 실패") == "배포 2026-09-26 실패"


def test_section_with_only_bullet_marker_is_empty():
    body = BODY.replace("- 배포 전 체크리스트가 필요함", "-")
    assert extract_sections(body).retrospective == ""


def test_select_issues_uses_half_open_interval_and_prefix():
    at_start = make_issue(PERIOD.start, number=1)
    inside = make_issue(datetime(2026, 10, 8, 12, tzinfo=KST), number=2)
    at_end = make_issue(PERIOD.end, number=3)
    before = make_issue(datetime(2026, 10, 4, 19, 59, tzinfo=KST), number=4)
    wrong_prefix = make_issue(datetime(2026, 10, 8, 12, tzinfo=KST), title="[Daily] 스크럼", number=5)

    selected = select_issues_in_period([at_end, wrong_prefix, inside, before, at_start], PERIOD)

    assert [issue.number for issue in selected] == [1, 2]


def test_parse_issue_from_github_json_handles_utc_and_missing_author():
    parsed = parse_issue_from_github_json(
        {
            "number": 7,
            "title": "[Troubleshooting] x",
            "author": None,
            "createdAt": "2026-10-05T01:30:00Z",
            "state": "CLOSED",
            "url": "https://github.com/o/r/issues/7",
            "body": None,
        }
    )
    assert parsed.author == ""
    assert parsed.body == ""
    assert parsed.created_at == datetime(2026, 10, 5, 1, 30, tzinfo=timezone.utc)


def test_extract_sections_recognizes_real_world_heading_variants():
    body = """# 2026-09-26 제목

## 🌱 등장 배경
- 배경 설명

## 🐞 문제 상황
- 마이그레이션 실패

## 🔍 원인 분석
- 테이블명 충돌

## ✅ 결정 및 대응
- 접두어를 붙임

## 회고
- 네이밍 규칙 필요
"""
    sections = extract_sections(body)
    assert sections.error == "- 마이그레이션 실패"
    assert sections.cause == "- 테이블명 충돌"
    assert sections.solution == "- 접두어를 붙임"
    assert sections.retrospective == "- 네이밍 규칙 필요"
    assert "배경 설명" not in (sections.error + sections.cause + sections.solution)
