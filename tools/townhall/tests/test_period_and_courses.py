from datetime import date, datetime, timedelta, timezone

import pytest

from townhall.courses import (
    COURSE_AI,
    COURSE_CLOUD,
    COURSE_FULLSTACK,
    COURSE_UNCLASSIFIED,
    classify_course,
)
from townhall.period import KST, compute_collection_period


def kst(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=KST)


def test_sunday_evening_run_uses_that_sunday_as_end():
    period = compute_collection_period(kst(2026, 10, 11, 20, 5))
    assert period.start == kst(2026, 10, 4, 20)
    assert period.end == kst(2026, 10, 11, 20)
    assert period.townhall_date == date(2026, 10, 12)


def test_end_is_fixed_regardless_of_run_time_on_sunday():
    early_period = compute_collection_period(kst(2026, 10, 11, 19, 0))
    late_period = compute_collection_period(kst(2026, 10, 11, 23, 59))
    assert early_period == late_period


def test_monday_rerun_keeps_previous_sunday_as_end():
    period = compute_collection_period(kst(2026, 10, 12, 9))
    assert period.end == kst(2026, 10, 11, 20)
    assert period.townhall_date == date(2026, 10, 12)


def test_saturday_uses_previous_sunday():
    period = compute_collection_period(kst(2026, 10, 10, 12))
    assert period.end == kst(2026, 10, 4, 20)


def test_utc_input_is_converted_to_kst():
    # 2026-10-11 11:00 UTC == 2026-10-11 20:00 KST (일요일)
    period = compute_collection_period(datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc))
    assert period.end == kst(2026, 10, 11, 20)


def test_utc_saturday_night_is_kst_sunday():
    # 2026-10-10 16:00 UTC == 2026-10-11 01:00 KST (일요일 새벽)
    period = compute_collection_period(datetime(2026, 10, 10, 16, 0, tzinfo=timezone.utc))
    assert period.end == kst(2026, 10, 11, 20)


def test_period_spans_exactly_seven_days():
    period = compute_collection_period(kst(2026, 10, 11, 20))
    assert period.end - period.start == timedelta(days=7)


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        compute_collection_period(datetime(2026, 10, 11, 20, 0))


def test_classify_course_maps_known_usernames():
    assert classify_course("rndnjsgud") == COURSE_FULLSTACK
    assert classify_course("kcr2120") == COURSE_FULLSTACK
    assert classify_course("whale5500d") == COURSE_AI
    assert classify_course("jiyoung720") == COURSE_AI
    assert classify_course("circlepaper") == COURSE_CLOUD


def test_classify_course_ignores_case_and_unknown_is_unclassified():
    assert classify_course("Whale5500D") == COURSE_AI
    assert classify_course("someone-else") == COURSE_UNCLASSIFIED
    assert classify_course("") == COURSE_UNCLASSIFIED
