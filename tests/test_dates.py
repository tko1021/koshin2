import datetime as dt

import pytest

from dips import dates


def test_excel_serial_known_anchor():
    # 2020-01-01 の Excel シリアルは 43831
    assert dates.excel_serial_to_date(43831) == dt.date(2020, 1, 1)
    # master ダミーの講習修了日 46183 = 2026-06-10
    assert dates.excel_serial_to_date(46183) == dt.date(2026, 6, 10)


def test_to_date_variants():
    assert dates.to_date(46183) == dt.date(2026, 6, 10)
    assert dates.to_date(dt.datetime(2026, 6, 10, 9, 0)) == dt.date(2026, 6, 10)
    assert dates.to_date("2026/06/10") == dt.date(2026, 6, 10)
    assert dates.to_date("2026-06-10") == dt.date(2026, 6, 10)
    assert dates.to_date("") is None
    assert dates.to_date(None) is None


def test_date_to_ymd_zero_padded():
    assert dates.date_to_ymd(dt.date(2026, 6, 9)) == "2026/06/09"
    assert dates.date_to_ymd(dt.date(2026, 12, 31)) == "2026/12/31"


def test_expiry_three_months_minus_one():
    # 発行日 2026-06-10 → +3か月 -1日 = 2026-09-09（ダミー実値と一致）
    assert dates.expiry_date(dt.date(2026, 6, 10)) == dt.date(2026, 9, 9)


def test_expiry_month_end_non_leap():
    # 11/30 + 3か月 = 2026-02-28（非うるう）→ -1 = 2026-02-27
    assert dates.expiry_date(dt.date(2025, 11, 30)) == dt.date(2026, 2, 27)


def test_expiry_leap_year():
    # 2023-11-30 + 3か月 = 2024-02-29（うるう）→ -1 = 2024-02-28
    assert dates.expiry_date(dt.date(2023, 11, 30)) == dt.date(2024, 2, 28)


def test_add_months_clamp_to_month_end():
    # 1/31 + 1か月 → 2月末
    assert dates.add_months(dt.date(2026, 1, 31), 1) == dt.date(2026, 2, 28)
    assert dates.add_months(dt.date(2024, 1, 31), 1) == dt.date(2024, 2, 29)


def test_business_days_basic():
    # 2024-01-01 は月曜。5営業日後は 2024-01-08（土日を除外）
    start = dt.date(2024, 1, 1)
    assert dates.add_business_days(start, 5, []) == dt.date(2024, 1, 8)


def test_business_days_with_holiday():
    start = dt.date(2024, 1, 1)
    holidays = [dt.date(2024, 1, 8)]  # 着地予定日が祝日
    assert dates.add_business_days(start, 5, holidays) == dt.date(2024, 1, 9)


def test_is_business_day():
    assert dates.is_business_day(dt.date(2024, 1, 1), []) is True   # Mon
    assert dates.is_business_day(dt.date(2024, 1, 6), []) is False  # Sat
    assert dates.is_business_day(dt.date(2024, 1, 7), []) is False  # Sun
    assert dates.is_business_day(dt.date(2024, 1, 1), [dt.date(2024, 1, 1)]) is False
