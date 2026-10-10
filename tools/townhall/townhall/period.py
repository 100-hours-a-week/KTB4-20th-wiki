"""타운홀 미팅 문서의 집계 기간과 미팅일을 계산하는 모듈."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

SUNDAY_WEEKDAY = 6
RUN_HOUR = 20
COLLECTION_DAYS = 7


@dataclass(frozen=True)
class CollectionPeriod:
    """집계 기간은 start 이상, end 미만임."""

    start: datetime
    end: datetime
    townhall_date: date


def compute_collection_period(now: datetime) -> CollectionPeriod:
    """now가 속한 실행 일요일 20:00(KST)을 끝으로 하는 7일 집계 기간을 반환함.

    일요일에는 그날 20:00(실행 시각 전후와 무관)이 끝이고, 월~토요일에는 직전 일요일 20:00이 끝임.
    끝 시각을 고정하므로 몇 시에 실행해도 결과가 같음. 타운홀 미팅일은 끝 날짜의 다음 날(월요일)임.
    """
    if now.tzinfo is None:
        raise ValueError("now는 timezone 정보가 있는 datetime이어야 함.")
    now_in_kst = now.astimezone(KST)
    days_since_sunday = (now_in_kst.weekday() - SUNDAY_WEEKDAY) % 7
    end_date = now_in_kst.date() - timedelta(days=days_since_sunday)
    end = datetime.combine(end_date, time(RUN_HOUR), tzinfo=KST)
    start = end - timedelta(days=COLLECTION_DAYS)
    return CollectionPeriod(start=start, end=end, townhall_date=end_date + timedelta(days=1))
