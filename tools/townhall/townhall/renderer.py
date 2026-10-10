"""과정별 항목들을 타운홀 미팅 Issue 본문으로 합치는 모듈."""

from townhall.courses import COURSE_ORDER, COURSE_UNCLASSIFIED

NO_ISSUE_TEXT = "(트러블 슈팅 내용 없음)"


def render_townhall_body(items_by_course: dict[str, list[str]]) -> str:
    """과정 순서대로 '## 과정명' 섹션을 만듦. 항목이 없는 과정은 안내 문구를 넣고, 미분류는 항목이 있을 때만 포함함."""
    section_texts = []
    for course in COURSE_ORDER:
        items = items_by_course.get(course, [])
        if course == COURSE_UNCLASSIFIED and not items:
            continue
        section_body = "\n\n".join(items) if items else NO_ISSUE_TEXT
        section_texts.append(f"## {course}\n\n{section_body}")
    return "\n\n".join(section_texts) + "\n"
