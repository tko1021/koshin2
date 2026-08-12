# -*- coding: utf-8 -*-
"""登録フォームの入力チェック（validators.validate_person_input）。"""
import datetime as dt

from dips import validators

TODAY = dt.date(2026, 8, 12)


def _v(**kw):
    args = {"name": "試験 太郎", "applicant_no": "A123456789",
            "complete_date": TODAY, "issue_date": TODAY, "phys_no": "", "koushi": ""}
    args.update(kw)
    return validators.validate_person_input(**args)


def test_valid_input_has_no_errors():
    assert _v() == []


def test_name_required():
    assert any("氏名" in m for m in _v(name="  "))


def test_applicant_no_required():
    assert any("技能証明申請者番号" in m for m in _v(applicant_no=""))


def test_applicant_no_rejects_fullwidth():
    assert any("半角" in m for m in _v(applicant_no="Ａ12345"))


def test_applicant_no_rejects_hyphen_and_space():
    assert any("半角" in m for m in _v(applicant_no="A123-456"))
    assert any("半角" in m for m in _v(applicant_no="A12 456"))


def test_applicant_no_rejects_over_10_chars():
    assert any("10文字以内" in m for m in _v(applicant_no="A1234567890"))


def test_issue_before_complete_is_error():
    errs = _v(complete_date=TODAY, issue_date=TODAY - dt.timedelta(days=1))
    assert any("修了日" in m and "前" in m for m in errs)


def test_issue_same_day_is_ok():
    assert _v(complete_date=TODAY, issue_date=TODAY) == []


def test_forbidden_chars_in_name():
    assert any("氏名" in m for m in _v(name='試験"太郎'))


def test_phys_no_blank_is_ok():
    assert _v(phys_no="") == []


def test_phys_no_rejects_non_ascii():
    assert any("身体適性" in m for m in _v(phys_no="ＰＡ00000"))


def test_koushi_forbidden_chars():
    assert any("担当講師" in m for m in _v(koushi="山田|講師"))
