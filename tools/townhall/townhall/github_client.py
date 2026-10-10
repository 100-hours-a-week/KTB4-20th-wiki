"""gh CLI로 wiki 레포의 Issue를 조회하고 생성하는 모듈."""

import json
import subprocess
from datetime import timezone
from typing import Callable

from townhall.issues import (
    TROUBLESHOOTING_TITLE_PREFIX,
    TroubleshootingIssue,
    parse_issue_from_github_json,
    select_issues_in_period,
)
from townhall.period import CollectionPeriod

CommandRunner = Callable[[list[str]], str]

DEFAULT_REPOSITORY = "100-hours-a-week/KTB4-20th-wiki"
ISSUE_FETCH_LIMIT = 200
ISSUE_JSON_FIELDS = "number,title,author,createdAt,state,url,body"


def run_gh_command(arguments: list[str]) -> str:
    """gh CLI를 실행하고 stdout을 반환함. 실패하면 stderr를 담아 예외를 냄."""
    completed_process = subprocess.run(
        ["gh", *arguments], capture_output=True, text=True, encoding="utf-8"
    )
    if completed_process.returncode != 0:
        raise RuntimeError(f"gh 실행 실패: {completed_process.stderr.strip()}")
    return completed_process.stdout


def _format_utc(moment) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class GitHubIssueClient:
    def __init__(self, repository: str = DEFAULT_REPOSITORY, run_command: CommandRunner = run_gh_command):
        self.repository = repository
        self.run_command = run_command

    def list_troubleshooting_issues(self, period: CollectionPeriod) -> list[TroubleshootingIssue]:
        """집계 기간에 생성된 [Troubleshooting] 이슈를 열림/닫힘 구분 없이 조회함.

        GitHub 검색은 부정확할 수 있어, 접두어와 기간(end 미만)은 로컬에서 다시 거름.
        """
        search_query = (
            f'"{TROUBLESHOOTING_TITLE_PREFIX}" in:title '
            f"created:{_format_utc(period.start)}..{_format_utc(period.end)}"
        )
        output_text = self.run_command(
            [
                "issue", "list", "--repo", self.repository, "--state", "all",
                "--search", search_query, "--json", ISSUE_JSON_FIELDS,
                "--limit", str(ISSUE_FETCH_LIMIT),
            ]
        )
        raw_issues = json.loads(output_text or "[]")
        if len(raw_issues) >= ISSUE_FETCH_LIMIT:
            raise RuntimeError(f"조회 결과가 {ISSUE_FETCH_LIMIT}건 한도에 도달해 누락 가능성이 있음.")
        issues = [parse_issue_from_github_json(raw_issue) for raw_issue in raw_issues]
        return select_issues_in_period(issues, period)

    def issue_title_exists(self, title: str) -> bool:
        """같은 제목의 Issue가 (열림/닫힘 무관) 이미 있는지 정확히 일치로 확인함."""
        output_text = self.run_command(
            [
                "issue", "list", "--repo", self.repository, "--state", "all",
                "--search", f'"{title}" in:title', "--json", "title", "--limit", "30",
            ]
        )
        return any(raw_issue["title"] == title for raw_issue in json.loads(output_text or "[]"))

    def create_issue(self, title: str, body: str) -> str:
        """Issue를 만들고 생성된 Issue의 URL을 반환함."""
        output_text = self.run_command(
            ["issue", "create", "--repo", self.repository, "--title", title, "--body", body]
        )
        return output_text.strip()
