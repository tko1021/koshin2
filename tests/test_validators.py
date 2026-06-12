import datetime as dt

from dips import validators as V


def test_forbidden_chars_detected():
    assert V.find_forbidden_chars("航空,太郎") == [","]
    assert set(V.find_forbidden_chars('a_b"c')) == {"_", '"'}
    # 日付以外では "/" も禁止
    assert "/" in V.find_forbidden_chars("2026/06/10", allow_slash=False)
    # 日付項目では "/" のみ許可
    assert V.find_forbidden_chars("2026/06/10", allow_slash=True) == []
    # ただし日付項目でも他の禁則文字は検出
    assert V.find_forbidden_chars("2026/06/10;", allow_slash=True) == [";"]


def test_ascii_alnum():
    assert V.ascii_alnum("ABCD1234567890") is None
    assert V.ascii_alnum("UC000026060001") is None
    assert V.ascii_alnum("航空") is not None
    assert V.ascii_alnum("") is not None


def test_max_len_10():
    assert V.max_len_10("1234567890") is None
    assert V.max_len_10("12345678901") is not None


def test_kikan_code_4digit():
    assert V.kikan_code_4digit("0000") is None
    assert V.kikan_code_4digit("123") is not None
    assert V.kikan_code_4digit("abcd") is not None


def test_shumeisho_no():
    assert V.shumeisho_no("UC000026060001") is None
    assert V.shumeisho_no("EL000026060001") is None
    assert V.shumeisho_no("XX000026060001") is not None
    assert V.shumeisho_no("UC12345") is not None
    assert V.shumeisho_no("UC0000260600011") is not None  # 13桁


def test_date_real():
    assert V.date_real("2026/06/10") is None
    assert V.date_real("2026/02/29") is not None  # 実在しない
    assert V.date_real("2024/02/29") is None      # うるう
    assert V.date_real("2026-06-10") is not None  # 区切り違い


def test_not_past():
    today = dt.date(2026, 6, 12)
    assert V.not_past("2026/06/12", today=today) is None  # 当日OK
    assert V.not_past("2026/06/13", today=today) is None
    assert V.not_past("2026/06/11", today=today) is not None


def test_one_of():
    assert V.one_of_12("1") is None and V.one_of_12("2") is None
    assert V.one_of_12("3") is not None
    assert V.one_of_123("3") is None
    assert V.one_of_123("4") is not None


def test_shumeisho_consistency():
    issue = dt.date(2026, 6, 10)
    assert V.check_shumeisho_consistency("UC000026060001", "0000", issue) == []
    # 機関コード不一致
    errs = V.check_shumeisho_consistency("UC123426060001", "0000", issue)
    assert any("機関コード" in e for e in errs)
    # 発行年月不一致（2025/06 のはずが番号は 2606）
    errs2 = V.check_shumeisho_consistency("UC000026060001", "0000", dt.date(2025, 6, 10))
    assert any("発行年月" in e for e in errs2)


def test_check_expiry():
    issue = dt.date(2026, 6, 10)
    assert V.check_expiry("2026/09/09", issue) == []
    assert V.check_expiry("2026/09/10", issue) != []
