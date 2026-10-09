"""명령줄 진입점: uv run python -m townhall [--dry-run]"""

import argparse
from datetime import datetime

from townhall.github_client import DEFAULT_REPOSITORY, GitHubIssueClient
from townhall.pipeline import RunStatus, run_townhall
from townhall.summarizer import TextGenerator

DEFAULT_MODEL_NAME = "gemini-3.1-flash-lite"

STATUS_MESSAGES = {
    RunStatus.DUPLICATE: "같은 제목의 Issue가 이미 있어 종료함.",
    RunStatus.NO_TARGETS: "집계 기간에 [Troubleshooting] 이슈가 없어 종료함.",
}


def create_gemini_text_generator(model_name: str) -> TextGenerator:
    """Gemini API로 텍스트를 생성하는 함수를 반환함. 첫 호출 때 클라이언트를 만들며 GEMINI_API_KEY를 사용함."""
    gemini_client = None

    def generate_text(prompt: str) -> str:
        nonlocal gemini_client
        if gemini_client is None:
            from google import genai  # 단위 테스트에서 SDK 없이 실행할 수 있도록 지연 import 함.

            gemini_client = genai.Client()
        response = gemini_client.models.generate_content(model=model_name, contents=prompt)
        return response.text or ""

    return generate_text


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(override=True)

    argument_parser = argparse.ArgumentParser(description="집계 기간의 트러블슈팅을 모아 타운홀 Issue를 게시함.")
    argument_parser.add_argument("--repo", default=DEFAULT_REPOSITORY, help="대상 wiki 레포 (owner/name)")
    argument_parser.add_argument("--model", default=DEFAULT_MODEL_NAME, help="요약에 쓸 Gemini 모델")
    argument_parser.add_argument("--dry-run", action="store_true", help="Issue를 만들지 않고 본문만 출력함")
    # 재실행과 테스트용 기준 시각. 일반 사용자에게는 노출하지 않음.
    argument_parser.add_argument("--now", help=argparse.SUPPRESS)
    parsed_arguments = argument_parser.parse_args()

    now = datetime.fromisoformat(parsed_arguments.now) if parsed_arguments.now else datetime.now().astimezone()
    result = run_townhall(
        now=now,
        client=GitHubIssueClient(parsed_arguments.repo),
        generate_text=create_gemini_text_generator(parsed_arguments.model),
        dry_run=parsed_arguments.dry_run,
    )

    if result.status in STATUS_MESSAGES:
        print(f"{result.title}: {STATUS_MESSAGES[result.status]}")
    elif result.status is RunStatus.DRY_RUN:
        print(f"# {result.title} (dry-run, 이슈 {result.issue_count}건)\n\n{result.body}")
    else:
        print(f"{result.title}: 이슈 {result.issue_count}건으로 게시함. {result.issue_url}")


if __name__ == "__main__":
    main()
