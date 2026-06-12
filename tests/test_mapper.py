"""build_row の統合テスト（実 mapping.yaml / code_map.yaml を使用）。"""
import datetime as dt

import pytest

from dips import config
from dips.excel_reader import flatten_header
from dips.mapper import build_row


@pytest.fixture(scope="module")
def cfg():
    settings = config.load_settings()
    mapping = config.load_mapping()
    code_map = config.load_code_map()
    return settings, mapping, code_map


def _record(**kwargs):
    """canonical なヘッダー名 → flatten キーの dict を作る。"""
    return {flatten_header(k): v for k, v in kwargs.items()}


def _dummy_taro():
    # master ダミー row4（航空太郎・二等・停止処分空欄）相当
    return _record(**{
        "申請ID(自動=証明書番号)": "UC000026060001",
        "技能証明申請者番号(10文字以内)": "1234567890",
        "事務所コード": "R0000001",
        "資格区分": "二等",
        "停止処分者向け講習受講": "",          # 空欄 → 無 → "1"
        "修了証明書番号(自動)": "UC000026060001",
        "講習修了日": 46183,                    # 2026/06/10
        "有効期間満了日(自動)": 46274,          # 2026/09/09
        "登録種別(状態フラグ)": "1：新規",
        "修了証明書発行日": 46183,
    })


def test_build_row_values(cfg):
    settings, mapping, code_map = cfg
    settings_values = {"kikan_code": "0000", "office_code_default": "R0000000"}
    res = build_row(_dummy_taro(), settings_values, code_map, mapping,
                    today=dt.date(2026, 6, 1))
    v = res.values
    assert len(v) == 17
    assert v[0] == "UC000026060001"        # 1 申請ID
    assert v[1] == "1234567890"            # 2 申請者番号
    assert v[2] == "0000"                  # 3 機関コード（設定B2）
    assert v[3] == "R0000001"              # 4 事務所コード（master）
    assert v[4] == "2"                     # 5 区分（二等→2）
    assert v[5] == "1"                     # 6 停止処分（空欄→無→1）
    assert v[6] == "PA000000000000"        # 7 検査証明書番号（固定）
    assert v[7:12] == ["", "", "", "", ""] # 8-12 空欄
    assert v[12] == "UC000026060001"       # 13 修了証明書番号
    assert v[13] == "2026/06/10"           # 14 修了日
    assert v[14] == "2026/09/09"           # 15 有効期間満了日
    assert v[15] == "1"                    # 16 状態フラグ
    assert v[16] == ""                     # 17 備考
    assert res.issue_date == dt.date(2026, 6, 10)


def test_build_row_no_errors_for_valid_record(cfg):
    settings, mapping, code_map = cfg
    settings_values = {"kikan_code": "0000", "office_code_default": "R0000000"}
    res = build_row(_dummy_taro(), settings_values, code_map, mapping,
                    today=dt.date(2026, 6, 1))
    assert res.errors == [], [(e.index, e.name, e.msg) for e in res.errors]


def test_office_code_falls_back_to_default(cfg):
    settings, mapping, code_map = cfg
    settings_values = {"kikan_code": "0000", "office_code_default": "R0000000"}
    rec = _dummy_taro()
    rec[flatten_header("事務所コード")] = ""   # 空 → 既定値へ
    res = build_row(rec, settings_values, code_map, mapping, today=dt.date(2026, 6, 1))
    assert res.values[3] == "R0000000"


def test_forbidden_char_in_name_is_flagged_only_on_that_field(cfg):
    # 申請IDにカンマが混入したケース（半角英数チェックと禁則文字の両方が立つ）
    settings, mapping, code_map = cfg
    settings_values = {"kikan_code": "0000", "office_code_default": "R0000000"}
    rec = _dummy_taro()
    rec[flatten_header("申請ID(自動=証明書番号)")] = "UC0000,2606"
    res = build_row(rec, settings_values, code_map, mapping, today=dt.date(2026, 6, 1))
    assert any("禁則文字" in e.msg and e.index == 1 for e in res.errors)
