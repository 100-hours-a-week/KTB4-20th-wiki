# townhall

wiki 레포의 `[Troubleshooting]` 이슈를 모아 `[Townhall] YYYY-MM-DD` Issue 1건을 만듦. 문제 정의는 `PROBLEM.md`를 참고함.

## 동작 요약

- 타운홀 미팅일은 월요일이고, 집계 기간은 직전 일요일 20:00(KST)까지의 7일임. 일요일 20:00에 실행하는 것을 전제로 함.
- 작성자 username으로 과정(풀스택/AI/클라우드)을 나누고, Gemini로 항목별 요약을 만든 뒤 Issue로 게시함.
- 같은 제목의 Issue가 있으면 새로 만들지 않고 종료함. 집계 대상이 없어도 만들지 않음.

## 실행 명령어

```bash
uv sync
uv run pytest                      # 단위 테스트 (LLM, GitHub 불필요)
uv run python -m townhall --dry-run   # 본문만 출력함. gh 로그인과 GEMINI_API_KEY 필요함
uv run python -m townhall             # Issue 게시
```

## 구조

| 모듈 | 역할 |
|---|---|
| `period.py` | 집계 기간, 타운홀 미팅일 계산 |
| `courses.py` | username → 과정 매핑 |
| `issues.py` | 이슈 모델, 기간 필터, 본문 섹션 추출 |
| `redaction.py` | 키/토큰, 이메일, IP, 내부 호스트 `[REDACTED]` 치환 |
| `summarizer.py` | 이슈별 요약, 양식 검증, 실패 시 자리표시자 |
| `renderer.py` | 과정별 섹션으로 본문 조립 |
| `github_client.py` | `gh` CLI로 Issue 조회, 생성 |
| `pipeline.py` | 전체 흐름 |
