"""日付・営業日ユーティリティ。

master の日付は Excel シリアル値（整数）か datetime で入りうるため、両対応する。
業務ルール:
  - 有効期間満了日 = 発行日の3か月後の前日（発行日 + 3か月 - 1日）
  - DIPS連携期限   = 発行日から5営業日（土日 + 祝日シートを除外）
"""
from __future__ import annotations

import calendar
import datetime as _dt
from typing import Iterable

# Excel(1900日付系, date1904=False) の起点。
# 1899-12-30 を起点にすると、近代日付では Excel の「1900年うるう年バグ」を
# 含めて正しいシリアル→日付変換になる（シリアル60=1900-02-29 の幻日以降）。
_EXCEL_EPOCH = _dt.date(1899, 12, 30)


def excel_serial_to_date(serial: int | float) -> _dt.date:
    """Excelシリアル値を date に変換する。"""
    return _EXCEL_EPOCH + _dt.timedelta(days=int(serial))


def to_date(value) -> _dt.date | None:
    """master セル値（datetime / Excelシリアル / 文字列）を date へ正規化する。

    解釈できない場合は None を返す。
    """
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, (int, float)):
        return excel_serial_to_date(value)
    s = str(value).strip()
    if not s:
        return None
    # "yyyy/mm/dd" / "yyyy-mm-dd"
    for sep in ("/", "-"):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                y, m, d = (int(p) for p in parts)
                try:
                    return _dt.date(y, m, d)
                except ValueError:
                    return None
    if s.isdigit():  # 文字列のシリアル値
        return excel_serial_to_date(int(s))
    return None


def date_to_ymd(d: _dt.date) -> str:
    """date を DIPS 形式 'yyyy/mm/dd'（ゼロ埋め）に整形する。"""
    return f"{d.year:04d}/{d.month:02d}/{d.day:02d}"


def add_months(d: _dt.date, months: int) -> _dt.date:
    """日付に月を加算する。加算先の月に同日が無ければ月末へ丸める。"""
    total = (d.year * 12 + (d.month - 1)) + months
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return _dt.date(year, month, min(d.day, last_day))


def expiry_date(issue: _dt.date, months: int = 3, minus_days: int = 1) -> _dt.date:
    """有効期間満了日 = 発行日 + months か月 - minus_days 日。"""
    return add_months(issue, months) - _dt.timedelta(days=minus_days)


def is_business_day(d: _dt.date, holidays: Iterable[_dt.date]) -> bool:
    """営業日判定（土日 + 祝日を除外）。"""
    if d.weekday() >= 5:  # 5=土, 6=日
        return False
    return d not in set(holidays)


def add_business_days(start: _dt.date, n: int, holidays: Iterable[_dt.date]) -> _dt.date:
    """start から n 営業日後の日付を返す（start 当日は数えない）。

    例: 発行日から5営業日 = add_business_days(発行日, 5, 祝日)。
    """
    hol = set(holidays)
    d = start
    count = 0
    while count < n:
        d += _dt.timedelta(days=1)
        if is_business_day(d, hol):
            count += 1
    return d
