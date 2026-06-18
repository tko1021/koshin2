"""Googleスプレッドシート（修了証明書発行台帳）連携。

サービスアカウント認証で gspread クライアントを生成し、seinodrone が作成済みの
既存スプレッドシートを ID（open_by_key）で開く。台帳ワークシート（無ければ作成）へ
ヘッダ初期化＆行追記する。スプレッドシート自体の新規作成は行わない。
"""
from __future__ import annotations

from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from . import config

# 既存シートをIDで開いて読み書きするだけなので spreadsheets スコープで足りる
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 台帳の列構成（修了証明書発行台帳・別添19に整合）
LEDGER_HEADER = [
    "修了証明書番号", "氏名", "生年月日", "区分", "限定解除事項", "修了日",
    "有効期限", "交付の有無", "再交付年月日", "担当講師", "登録更新講習機関コード", "備考",
]


def _credentials() -> Credentials:
    """認証情報を取得。クラウドは Streamlit Secrets、ローカルは鍵ファイル。"""
    # クラウド: st.secrets["gcp_service_account"]（TOMLのテーブル）
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:  # noqa: BLE001 streamlit外/未設定はローカルへ
        pass
    # ローカル: secrets/service_account.json
    sa = config.SERVICE_ACCOUNT_FILE
    if not Path(sa).exists():
        raise FileNotFoundError(
            f"サービスアカウント鍵が見つかりません: {sa}\n"
            "ローカルは secrets/service_account.json、クラウドは Secrets の "
            "[gcp_service_account] を設定してください。")
    return Credentials.from_service_account_file(str(sa), scopes=SCOPES)


def get_client() -> gspread.Client:
    return gspread.authorize(_credentials())


def open_spreadsheet(sheet_id: str | None = None):
    """既存スプレッドシートを ID で開く（新規作成はしない）。"""
    sheet_id = (sheet_id or config.get_sheet_id() or "").strip()
    if not sheet_id:
        raise ValueError(
            "SHEET_ID が未設定です。環境変数 KOSHIN_SHEET_ID か "
            "settings.yaml の sheets.spreadsheet_id を設定してください。")
    return get_client().open_by_key(sheet_id)


def get_or_create_worksheet(ss, title: str):
    """台帳ワークシートを取得（無ければ作成）し、1行目ヘッダを初期化して返す。"""
    try:
        ws = ss.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=1000, cols=len(LEDGER_HEADER))
    header = ws.row_values(1)
    if not any(header):                       # 空シートのときだけヘッダを書く
        ws.update(range_name="A1", values=[LEDGER_HEADER])
    return ws


def _cell(v) -> str:
    return "" if v is None else str(v)


def append_ledger_rows(rows: list[dict], sheet_id: str | None = None,
                       worksheet: str = "修了証明書発行台帳") -> int:
    """台帳ワークシートへ rows（LEDGER_HEADER キーの dict）を追記。返り値=追記件数。"""
    ss = open_spreadsheet(sheet_id)
    ws = get_or_create_worksheet(ss, worksheet)
    values = [[_cell(r.get(h, "")) for h in LEDGER_HEADER] for r in rows]
    if values:
        # 台帳は記録の原本。RAW で入力値をそのまま保存し、機関コードの先頭ゼロ
        # （例 "0188"→188）や日付文字列がシート側で再解釈されるのを防ぐ。
        ws.append_rows(values, value_input_option="RAW")
    return len(values)
