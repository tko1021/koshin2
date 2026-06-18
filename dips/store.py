# -*- coding: utf-8 -*-
"""クラウド版データ層：Googleスプレッドシートに修了者マスタと発行履歴を保存する。

ローカル版の master.xlsx / export_log.csv に相当する役割を、Googleシートで提供する。
派生値（修了証明書番号・有効期限・各コード・固有番号）はシートには保存せず、
読み出し後に Python（intake/dates）で計算する方針。

- ワークシート「修了者マスタ」: 1行=1修了者の入力項目（MASTER_HEADER の列）
- ワークシート「発行履歴」    : DIPS CSV発行の履歴（HISTORY_HEADER の列）
"""
from __future__ import annotations

import gspread

from . import sheets

# 修了者マスタ（入力項目のみ。派生値はPython計算）
MASTER_WS = "修了者マスタ"
MASTER_HEADER = [
    "講習区分", "等級区分", "技能証明申請者番号", "氏名", "生年月日", "住所",
    "停止処分者向け講習受講有無", "修了日", "証明書発行日", "状態",
    "身体適性検査証明書番号", "担当講師",
    "限定解除（回転翼マルチ）", "限定解除（回転翼ヘリ）", "限定解除（飛行機）",
]

# 発行履歴（重複除外・状態フラグ整合に使用）
HISTORY_WS = "発行履歴"
HISTORY_HEADER = ["日時", "氏名", "申請ID", "修了証明書番号", "状態フラグ", "ファイル名"]


def _spreadsheet(sheet_id: str | None = None):
    return sheets.open_spreadsheet(sheet_id)


def get_or_create_ws(ss, title: str, header: list[str]):
    try:
        ws = ss.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=1000, cols=max(len(header), 10))
    cur = ws.row_values(1)
    if not any(cur):
        ws.update(range_name="A1", values=[header])
    return ws


# ---------- 修了者マスタ ----------
def master_ws(sheet_id: str | None = None):
    return get_or_create_ws(_spreadsheet(sheet_id), MASTER_WS, MASTER_HEADER)


def read_people(sheet_id: str | None = None) -> list[dict]:
    """修了者マスタを読み、各行を dict で返す（_row=シート行番号 2始まり）。"""
    ws = master_ws(sheet_id)
    rows = ws.get_all_values()
    out = []
    for i, row in enumerate(rows[1:], start=2):       # 1行目=ヘッダ
        if not any(c.strip() for c in row):
            continue
        d = {h: (row[j] if j < len(row) else "") for j, h in enumerate(MASTER_HEADER)}
        d["_row"] = i
        out.append(d)
    return out


def append_person(values: dict, sheet_id: str | None = None) -> int:
    """1名を末尾に追記。返り値=追記した行番号。"""
    ws = master_ws(sheet_id)
    row = [str(values.get(h, "") or "") for h in MASTER_HEADER]
    ws.append_row(row, value_input_option="RAW")
    return len(ws.get_all_values())


def update_person(rownum: int, values: dict, sheet_id: str | None = None) -> None:
    """指定行を上書き更新。"""
    ws = master_ws(sheet_id)
    row = [str(values.get(h, "") or "") for h in MASTER_HEADER]
    end_col = gspread.utils.rowcol_to_a1(rownum, len(MASTER_HEADER))
    ws.update(range_name=f"A{rownum}:{end_col}", values=[row], value_input_option="RAW")


def delete_person(rownum: int, sheet_id: str | None = None) -> None:
    """指定行を削除（以降の行が繰り上がる）。"""
    master_ws(sheet_id).delete_rows(rownum)


# ---------- 発行履歴 ----------
def history_ws(sheet_id: str | None = None):
    return get_or_create_ws(_spreadsheet(sheet_id), HISTORY_WS, HISTORY_HEADER)


def read_history(sheet_id: str | None = None) -> list[dict]:
    ws = history_ws(sheet_id)
    rows = ws.get_all_values()
    out = []
    for row in rows[1:]:
        if not any(c.strip() for c in row):
            continue
        out.append({h: (row[j] if j < len(row) else "") for j, h in enumerate(HISTORY_HEADER)})
    return out


def append_history(entries: list[dict], sheet_id: str | None = None) -> int:
    ws = history_ws(sheet_id)
    rows = [[str(e.get(h, "") or "") for h in HISTORY_HEADER] for e in entries]
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
    return len(rows)


# ---------- 印影画像（Base64をシートに保存。1セル上限50000字のため分割） ----------
SEAL_WS = "_seal"
_SEAL_CHUNK = 40000


def set_seal_b64(b64: str, sheet_id: str | None = None) -> int:
    """印影のBase64をシート「_seal」のA列に分割保存（公開リポジトリに載せないため）。"""
    ss = _spreadsheet(sheet_id)
    try:
        ws = ss.worksheet(SEAL_WS)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=SEAL_WS, rows=50, cols=1)
    chunks = [b64[i:i + _SEAL_CHUNK] for i in range(0, len(b64), _SEAL_CHUNK)] or [""]
    ws.update(range_name=f"A1:A{len(chunks)}", values=[[c] for c in chunks],
              value_input_option="RAW")
    return len(chunks)


def get_seal_b64(sheet_id: str | None = None) -> str:
    """シート「_seal」A列の分割Base64を連結して返す（無ければ空）。"""
    ss = _spreadsheet(sheet_id)
    try:
        ws = ss.worksheet(SEAL_WS)
    except gspread.WorksheetNotFound:
        return ""
    return "".join(ws.col_values(1))
