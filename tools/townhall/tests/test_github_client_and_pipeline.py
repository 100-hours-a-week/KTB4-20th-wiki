import json
from datetime import datetime

import pytest

from townhall.github_client import ISSUE_FETCH_LIMIT, GitHubIssueClient
from townhall.period import KST, compute_collection_period
from townhall.pipeline import AllSummariesFailedError, RunStatus, run_townhall
from townhall.summarizer import DIFFICULTY_HEADING, LESSON_HEADING, RESOLUTION_HEADING

SUNDAY_EVENING = datetime(2026, 10, 11, 20, 1, tzinfo=KST)

VALID_SUMMARY = f"""{DIFFICULTY_HEADING}
- 어려움

{RESOLUTION_HEADING}
- 해결

{LESSON_HEADING}
- 배움
"""


def raw_issue(number, author, created_at, title="[Troubleshooting] 이슈"):
    return {
        "number": number,
        "title": f"{title} {number}",
        "author": {"login": author},
        "createdAt": created_at,
        "state": "OPEN",
        "url": f"https://github.com/o/r/issues/{number}",
        "body": "## 🐞 에러 내용\n- e\n## 🔍 원인 분석\n- c\n## ✅ 해결 방법\n- s\n## 회고\n- r\n",
    }


class FakeCommandRunner:
    def __init__(self, list_output=None, existing_titles=()):
        self.list_output = list_output if list_output is not None else []
        self.existing_titles = existing_titles
        self.calls = []

    def __call__(self, arguments):
        self.calls.append(arguments)
        if arguments[:2] == ["issue", "create"]:
            return "https://github.com/o/r/issues/99\n"
        if "--search" in arguments and "title" == arguments[arguments.index("--json") + 1]:
            return json.dumps([{"title": title} for title in self.existing_titles])
        return json.dumps(self.list_output)

    def created_calls(self):
        return [call for call in self.calls if call[:2] == ["issue", "create"]]


def fake_text_generator(prompt):
    return VALID_SUMMARY


def test_list_query_uses_utc_period_and_all_states():
    runner = FakeCommandRunner()
    GitHubIssueClient("o/r", runner).list_troubleshooting_issues(compute_collection_period(SUNDAY_EVENING))
    search_query = runner.calls[0][runner.calls[0].index("--search") + 1]
    assert "created:2026-10-04T11:00:00Z..2026-10-11T11:00:00Z" in search_query
    assert runner.calls[0][runner.calls[0].index("--state") + 1] == "all"


def test_list_raises_when_fetch_limit_is_reached():
    many_issues = [raw_issue(i, "whale5500d", "2026-10-05T01:00:00Z") for i in range(ISSUE_FETCH_LIMIT)]
    client = GitHubIssueClient("o/r", FakeCommandRunner(list_output=many_issues))
    with pytest.raises(RuntimeError):
        client.list_troubleshooting_issues(compute_collection_period(SUNDAY_EVENING))


def test_issue_title_exists_requires_exact_match():
    client = GitHubIssueClient("o/r", FakeCommandRunner(existing_titles=["[Townhall] 2026-10-12 (복사본)"]))
    assert client.issue_title_exists("[Townhall] 2026-10-12") is False
    client = GitHubIssueClient("o/r", FakeCommandRunner(existing_titles=["[Townhall] 2026-10-12"]))
    assert client.issue_title_exists("[Townhall] 2026-10-12") is True


def test_pipeline_publishes_one_issue_grouped_by_course():
    runner = FakeCommandRunner(
        list_output=[
            raw_issue(1, "whale5500d", "2026-10-05T01:00:00Z"),
            raw_issue(2, "circlepaper", "2026-10-06T01:00:00Z"),
            raw_issue(3, "stranger", "2026-10-07T01:00:00Z"),
            raw_issue(4, "kcr2120", "2026-10-12T01:00:00Z"),  # 집계 기간 밖
        ]
    )

    result = run_townhall(SUNDAY_EVENING, GitHubIssueClient("o/r", runner), fake_text_generator)

    assert result.status is RunStatus.PUBLISHED
    assert result.title == "[Townhall] 2026-10-12"
    assert result.issue_count == 3
    assert result.issue_url == "https://github.com/o/r/issues/99"
    assert len(runner.created_calls()) == 1
    assert "## 풀스택\n\n(트러블 슈팅 내용 없음)" in result.body
    assert "## 미분류" in result.body
    assert "issues/4" not in result.body


def test_pipeline_skips_without_calling_model_when_title_exists():
    runner = FakeCommandRunner(existing_titles=["[Townhall] 2026-10-12"])

    def forbidden_generator(prompt):
        raise AssertionError("중복이면 모델을 호출하면 안 됨")

    result = run_townhall(SUNDAY_EVENING, GitHubIssueClient("o/r", runner), forbidden_generator)

    assert result.status is RunStatus.DUPLICATE
    assert runner.created_calls() == []


def test_pipeline_creates_nothing_when_no_targets():
    runner = FakeCommandRunner(list_output=[])
    result = run_townhall(SUNDAY_EVENING, GitHubIssueClient("o/r", runner), fake_text_generator)
    assert result.status is RunStatus.NO_TARGETS
    assert runner.created_calls() == []


def test_pipeline_dry_run_returns_body_without_creating():
    runner = FakeCommandRunner(list_output=[raw_issue(1, "whale5500d", "2026-10-05T01:00:00Z")])
    result = run_townhall(SUNDAY_EVENING, GitHubIssueClient("o/r", runner), fake_text_generator, dry_run=True)
    assert result.status is RunStatus.DRY_RUN
    assert result.body
    assert runner.created_calls() == []


def test_pipeline_continues_with_placeholder_when_one_summary_fails():
    runner = FakeCommandRunner(
        list_output=[
            raw_issue(1, "whale5500d", "2026-10-05T01:00:00Z"),
            raw_issue(2, "whale5500d", "2026-10-06T01:00:00Z"),
        ]
    )
    responses = iter([VALID_SUMMARY, "엉뚱한 응답"])

    result = run_townhall(SUNDAY_EVENING, GitHubIssueClient("o/r", runner), lambda prompt: next(responses))

    assert result.status is RunStatus.PUBLISHED
    assert "(요약 실패: https://github.com/o/r/issues/2)" in result.body
    assert "- 배움" in result.body


def test_pipeline_refuses_to_publish_when_every_summary_fails():
    runner = FakeCommandRunner(
        list_output=[
            raw_issue(1, "whale5500d", "2026-10-05T01:00:00Z"),
            raw_issue(2, "circlepaper", "2026-10-06T01:00:00Z"),
        ]
    )

    def broken_generator(prompt):
        raise RuntimeError("API key not valid")

    with pytest.raises(AllSummariesFailedError):
        run_townhall(SUNDAY_EVENING, GitHubIssueClient("o/r", runner), broken_generator)
    assert runner.created_calls() == []
