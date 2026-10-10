"""이슈 작성자의 GitHub username을 과정(풀스택/AI/클라우드)에 매핑하는 모듈."""

COURSE_FULLSTACK = "풀스택"
COURSE_AI = "AI"
COURSE_CLOUD = "클라우드"
COURSE_UNCLASSIFIED = "미분류"

COURSE_ORDER = (COURSE_FULLSTACK, COURSE_AI, COURSE_CLOUD, COURSE_UNCLASSIFIED)

USERNAME_TO_COURSE = {
    "rndnjsgud": COURSE_FULLSTACK,
    "kcr2120": COURSE_FULLSTACK,
    "whale5500d": COURSE_AI,
    "jiyoung720": COURSE_AI,
    "circlepaper": COURSE_CLOUD,
}


def classify_course(github_username: str) -> str:
    """username(대소문자 무시)에 해당하는 과정명을 반환하고, 매핑에 없으면 '미분류'를 반환함."""
    return USERNAME_TO_COURSE.get(github_username.strip().lower(), COURSE_UNCLASSIFIED)
