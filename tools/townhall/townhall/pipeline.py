"""집계 기간 계산부터 요약, 렌더링, 게시까지 한 번에 수행하는 모듈."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from townhall.courses import classify_course
from townhall.issues import TroubleshootingIssue
from townhall.period import CollectionPeriod, compute_collection_period
from townhall.renderer import render_townhall_body
from townhall.summarizer import TextGenerator, summarize_issue_safely

TOWNHALL_TITLE_PREFIX = "[Townhall]"


class AllSummariesFailedError(RuntimeError):
    """모든 이슈의 요약이 실패한 경우. 자리표시자뿐인 Issue를 게시하지 않기 위해 실행을 실패 처리함."""


class RunStatus(Enum):
    PUBLISHED = "published"
    DRY_RUN = "dry_run"
    DUPLICATE = "duplicate"
    NO_TARGETS = "no_targets"


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    title: str
    body: str | None = None
    issue_count: int = 0
    issue_url: str | None = None


class IssueClient(Protocol):
    def list_troubleshooting_issues(self, period: CollectionPeriod) -> list[TroubleshootingIssue]: ...
    def issue_title_exists(self, title: str) -> bool: ...
    def create_issue(self, title: str, body: str) -> str: ...


def build_townhall_title(period: CollectionPeriod) -> str:
    return f"{TOWNHALL_TITLE_PREFIX} {period.townhall_date.isoformat()}"


def run_townhall(
    now: datetime,
    client: IssueClient,
    generate_text: TextGenerator,
    dry_run: bool = False,
) -> RunResult:
    """같은 제목이 있으면 종료하고, 대상이 없으면 Issue를 만들지 않으며, 그 외에는 과정별로 요약해 게시함."""
    period = compute_collection_period(now)
    title = build_townhall_title(period)

    if client.issue_title_exists(title):
        return RunResult(status=RunStatus.DUPLICATE, title=title)

    issues = client.list_troubleshooting_issues(period)
    if not issues:
        return RunResult(status=RunStatus.NO_TARGETS, title=title)

    items_by_course: dict[str, list[str]] = {}
    succeeded_count = 0
    for issue in issues:
        course = classify_course(issue.author)
        outcome = summarize_issue_safely(issue, generate_text)
        items_by_course.setdefault(course, []).append(outcome.item_text)
        succeeded_count += outcome.succeeded
    if succeeded_count == 0:
        raise AllSummariesFailedError(
            f"이슈 {len(issues)}건의 요약이 모두 실패해 게시하지 않음. API 키와 모델 설정을 확인할 것."
        )
    body = render_townhall_body(items_by_course)

    if dry_run:
        return RunResult(status=RunStatus.DRY_RUN, title=title, body=body, issue_count=len(issues))
    issue_url = client.create_issue(title, body)
    return RunResult(
        status=RunStatus.PUBLISHED, title=title, body=body, issue_count=len(issues), issue_url=issue_url
    )
