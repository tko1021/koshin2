# -*- coding: utf-8 -*-
"""帳票（修了者名簿・講習実施記録）の生成テスト。"""
import datetime as dt

from openpyxl import load_workbook

from dips import reports

ORG = {"kikan_name": "テスト機関", "kikan_code": "0188"}

PEOPLE = [
    {"cert_no": "UC018825060001", "applicant_no": "A000000001", "name": "山田　太郎",
     "birth": "1990/01/02", "koushu": "更新講習", "grade": "一等",
     "complete_date": "2025/06/01", "issue_date": "2025/06/02",
     "expiry": "2025/09/01", "koushi": "鈴木一郎",
     "gentei_map": {"回転翼航空機（マルチ）": ["基本", "目視外飛行"],
                    "回転翼航空機（ヘリ）": [], "飛行機": []}},
    {"cert_no": "UC018825060002", "applicant_no": "A000000002", "name": "佐藤　花子",
     "birth": "1985/12/31", "koushu": "更新講習", "grade": "二等",
     "complete_date": "2025/06/01", "issue_date": "2025/06/02",
     "expiry": "2025/09/01", "koushi": "鈴木一郎",
     "gentei_map": {"回転翼航空機（マルチ）": [], "回転翼航空機（ヘリ）": [], "飛行機": []}},
    {"cert_no": "EL018825070001", "applicant_no": "A000000003", "name": "田中　次郎",
     "birth": "2000/05/05", "koushu": "失効再交付講習", "grade": "二等",
     "complete_date": "2025/07/10", "issue_date": "2025/07/11",
     "expiry": "2025/10/10", "koushi": "高橋三郎",
     "gentei_map": {"回転翼航空機（マルチ）": [], "回転翼航空機（ヘリ）": [], "飛行機": []}},
]


def test_build_roster_rows_numbers_and_gentei():
    rows = reports.build_roster_rows(PEOPLE)
    assert [r["no"] for r in rows] == [1, 2, 3]
    assert rows[0]["name"] == "山田　太郎"
    # 限定解除は certificate.display_gentei と同じ表記（目視外→目視内・基本は常時先頭）
    assert rows[0]["gentei"] == "基本・目視内飛行（限定解除）"
    assert rows[1]["gentei"] == "基本"


def test_build_roster_rows_keeps_given_gentei_text():
    rows = reports.build_roster_rows([{**PEOPLE[0], "gentei": "既定文字列"}])
    assert rows[0]["gentei"] == "既定文字列"


def test_filter_by_period_inclusive_and_renumber():
    rows = reports.build_roster_rows(PEOPLE)
    kept = reports.filter_by_period(rows, dt.date(2025, 6, 1), dt.date(2025, 6, 1))
    assert [r["name"] for r in kept] == ["山田　太郎", "佐藤　花子"]
    assert [r["no"] for r in kept] == [1, 2]
    # 元のリストは変更しない
    assert [r["no"] for r in rows] == [1, 2, 3]


def test_filter_by_period_open_ended():
    rows = reports.build_roster_rows(PEOPLE)
    assert len(reports.filter_by_period(rows, dt.date(2025, 7, 1), None)) == 1
    assert len(reports.filter_by_period(rows, None, dt.date(2025, 6, 30))) == 2
    assert len(reports.filter_by_period(rows, None, None)) == 3


def test_build_record_rows_groups_by_date_and_kubun():
    recs = reports.build_record_rows(reports.build_roster_rows(PEOPLE))
    assert len(recs) == 2
    first = recs[0]
    assert first["date"] == "2025/06/01"
    assert first["koushu"] == "更新講習"
    assert (first["grade1"], first["grade2"], first["total"]) == (1, 1, 2)
    assert first["koushi"] == "鈴木一郎"          # 重複講師はまとめる
    assert first["names"] == "山田　太郎、佐藤　花子"
    assert recs[1]["total"] == 1


def test_parse_date():
    assert reports.parse_date("2025/06/01") == dt.date(2025, 6, 1)
    assert reports.parse_date("2025-06-01") == dt.date(2025, 6, 1)
    assert reports.parse_date("") is None
    assert reports.parse_date("2025/13/01") is None


def test_roster_pdf_and_record_pdf(tmp_path):
    rows = reports.build_roster_rows(PEOPLE)
    p1 = reports.roster_pdf(rows, tmp_path / "名簿.pdf", ORG, period="全期間")
    p2 = reports.record_pdf(reports.build_record_rows(rows),
                            tmp_path / "記録.pdf", ORG, period="全期間")
    for p in (p1, p2):
        assert p.exists() and p.stat().st_size > 1000
        assert p.read_bytes().startswith(b"%PDF")


def test_pdf_with_no_rows(tmp_path):
    p = reports.roster_pdf([], tmp_path / "空.pdf", ORG)
    assert p.exists() and p.read_bytes().startswith(b"%PDF")


def test_roster_xlsx(tmp_path):
    rows = reports.build_roster_rows(PEOPLE)
    out = reports.roster_xlsx(rows, tmp_path / "名簿.xlsx", ORG, period="全期間")
    ws = load_workbook(out).active
    assert ws.title == "修了者名簿"
    assert ws.cell(row=1, column=1).value == reports.ROSTER_TITLE
    # 5行目=ヘッダ、6行目以降=データ
    assert ws.cell(row=5, column=1).value == "No"
    assert ws.cell(row=5, column=4).value == "氏名"
    assert ws.cell(row=6, column=4).value == "山田　太郎"
    assert ws.cell(row=8, column=9).value == "EL018825070001"
    # 末尾に限定解除事項の列がある
    last = ws.max_column
    assert ws.cell(row=5, column=last).value == "限定解除事項"
    assert ws.cell(row=6, column=last).value == "基本・目視内飛行（限定解除）"


def test_record_xlsx(tmp_path):
    recs = reports.build_record_rows(reports.build_roster_rows(PEOPLE))
    out = reports.record_xlsx(recs, tmp_path / "記録.xlsx", ORG)
    ws = load_workbook(out).active
    assert ws.title == "講習実施記録"
    assert ws.cell(row=6, column=2).value == "2025/06/01"
    assert ws.cell(row=6, column=6).value == 2


def test_creates_parent_directory(tmp_path):
    out = reports.roster_xlsx(reports.build_roster_rows(PEOPLE),
                              tmp_path / "深い" / "階層" / "名簿.xlsx", ORG)
    assert out.exists()
