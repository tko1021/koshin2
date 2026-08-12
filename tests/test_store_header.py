# -*- coding: utf-8 -*-
"""store の列突合（ヘッダー名ベース）とグリッド拡張の検証。

修了者マスタの列が入れ替わっていたり、独自の列が足されていたり、列名に
空白が入っていても、正しい列に読み書きできることを確かめる。
"""
from __future__ import annotations

import gspread
import pytest

from dips import store


class FakeWS:
    def __init__(self, title="修了者マスタ", rows=None, col_count=30, row_count=1000):
        self.title = title
        self._rows = [list(r) for r in (rows or [])]
        self.col_count = col_count
        self.row_count = row_count
        self.resized_to = None

    def row_values(self, r):
        return list(self._rows[r - 1]) if len(self._rows) >= r else []

    def get_all_values(self):
        return [list(r) for r in self._rows]

    def resize(self, rows=None, cols=None):
        self.resized_to = (rows, cols)
        self.col_count = cols or self.col_count
        self.row_count = rows or self.row_count

    def update(self, range_name=None, values=None, value_input_option=None, **kw):
        if range_name == "A1":
            if self._rows:
                self._rows[0] = list(values[0])
            else:
                self._rows.append(list(values[0]))
            return {}
        r = int("".join(c for c in range_name.split(":")[0] if c.isdigit()))
        while len(self._rows) < r:
            self._rows.append([])
        self._rows[r - 1] = list(values[0])
        return {}

    def append_row(self, values, value_input_option=None, **kw):
        self._rows.append(list(values))
        return {}


class FakeSS:
    def __init__(self, ws=None):
        self._ws = {ws.title: ws} if ws else {}

    def worksheet(self, title):
        if title not in self._ws:
            raise gspread.WorksheetNotFound(title)
        return self._ws[title]

    def add_worksheet(self, title, rows, cols):
        ws = FakeWS(title=title, col_count=cols, row_count=rows)
        self._ws[title] = ws
        return ws


H = store.MASTER_HEADER


def _use(monkeypatch, ws):
    monkeypatch.setattr(store, "_spreadsheet", lambda sheet_id=None: FakeSS(ws))
    return ws


def _person(name="試験 太郎", appno="A123456789"):
    return {h: "" for h in H} | {
        "講習区分": "更新講習", "等級区分": "一等", "技能証明申請者番号": appno,
        "氏名": name, "修了日": "2026/08/12", "証明書発行日": "2026/08/12",
        "状態": "新規", "停止処分者向け講習受講有無": "無",
    }


def test_append_follows_actual_column_order(monkeypatch):
    """列が入れ替わっていても、ヘッダー名の位置へ書き込む。"""
    shuffled = [H[3], H[0], H[2]] + [h for h in H if h not in (H[0], H[2], H[3])]
    ws = _use(monkeypatch, FakeWS(rows=[shuffled]))
    store.append_person(_person())
    written = ws.get_all_values()[1]
    assert written[shuffled.index("氏名")] == "試験 太郎"
    assert written[shuffled.index("技能証明申請者番号")] == "A123456789"
    assert written[shuffled.index("講習区分")] == "更新講習"


def test_read_follows_actual_column_order(monkeypatch):
    shuffled = [H[3], H[0], H[2]] + [h for h in H if h not in (H[0], H[2], H[3])]
    row = [""] * len(shuffled)
    row[shuffled.index("氏名")] = "試験 花子"
    row[shuffled.index("証明書発行日")] = "2026/08/12"
    _use(monkeypatch, FakeWS(rows=[shuffled, row]))
    people = store.read_people()
    assert people[0]["氏名"] == "試験 花子"
    assert people[0]["証明書発行日"] == "2026/08/12"
    assert people[0]["_row"] == 2


def test_header_matching_ignores_whitespace(monkeypatch):
    """「停止処分者向け講習 受講有無」のような空白入りの列名でも突合できる。"""
    head = list(H)
    head[6] = "停止処分者向け講習　受講有無"
    ws = _use(monkeypatch, FakeWS(rows=[head]))
    store.append_person(_person())
    assert ws.get_all_values()[1][6] == "無"


def test_extra_columns_are_preserved_on_update(monkeypatch):
    """シートに独自に足した列（備考など）を更新で消さない。"""
    head = list(H) + ["備考"]
    row = [""] * len(H) + ["手書きメモ"]
    ws = _use(monkeypatch, FakeWS(rows=[head, row]))
    store.update_person(2, _person(name="更新後"))
    assert ws.get_all_values()[1][-1] == "手書きメモ"
    assert ws.get_all_values()[1][H.index("氏名")] == "更新後"


def test_missing_column_raises_actionable_error(monkeypatch):
    _use(monkeypatch, FakeWS(rows=[[h for h in H if h != "証明書発行日"]]))
    with pytest.raises(RuntimeError) as ei:
        store.append_person(_person())
    assert "証明書発行日" in str(ei.value)


def test_narrow_worksheet_is_widened(monkeypatch):
    """列数がヘッダーより少ないシートは追記前に広げる（grid limits 対策）。"""
    ws = _use(monkeypatch, FakeWS(rows=[list(H)], col_count=12))
    store.append_person(_person())
    assert ws.resized_to == (1000, len(H))


def test_new_worksheet_gets_header(monkeypatch):
    monkeypatch.setattr(store, "_spreadsheet", lambda sheet_id=None: FakeSS())
    assert store.read_people() == []
