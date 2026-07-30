# -*- coding: utf-8 -*-
"""master.xlsx の修了者から帳票（修了者名簿・講習実施記録）を作成するページ。

- 期間で絞り込み、PDF（A4横）と Excel を生成
- 保存先: 共有フォルダ（data_dir）の「帳票」フォルダ
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st
from openpyxl import load_workbook

from dips import config, dates, intake, reports

st.set_page_config(page_title="帳票作成", layout="wide")

settings, mapping, code_map, paths = config.load_all()
org = settings.get("organization", {})
kikan = org.get("kikan_code", "")
MASTER = paths.master
SHEET = "修了者"
MONTHS = settings["validity"]["months"]
MINUS = settings["validity"]["minus_days"]
REPORT_DIR = Path(paths.data_dir) / "帳票"
PREFIX = {"更新講習": "UC", "失効再交付講習": "EL"}
GENTEI_COLS = {"回転翼航空機（マルチ）": 22, "回転翼航空機（ヘリ）": 23, "飛行機": 24}


def read_people(ws):
    """修了者シートを読み、証明書番号などの派生値を付けて返す。

    証明書番号は「同一発行年月の入力順」で採番されるため、絞り込み前に
    シート全行を通して採番する（発行ページと同じ結果になる）。
    """
    out = []
    serial_by_ym: dict[str, int] = {}
    r = 2
    while ws.cell(row=r, column=1).value or ws.cell(row=r, column=4).value:
        issue = dates.to_date(ws.cell(row=r, column=9).value)
        if issue is None:
            r += 1
            continue
        koushu = ws.cell(row=r, column=1).value or "更新講習"
        ym = f"{issue.year % 100:02d}{issue.month:02d}"
        serial_by_ym[ym] = serial_by_ym.get(ym, 0) + 1
        cert_no = intake.build_shumeisho_no(PREFIX.get(koushu, "UC"), kikan, issue,
                                            serial_by_ym[ym])

        def _split(col):
            v = ws.cell(row=r, column=col).value
            return [s for s in str(v).replace(",", "、").split("、") if s.strip()] if v else []

        birth = dates.to_date(ws.cell(row=r, column=5).value)
        out.append({
            "cert_no": cert_no,
            "applicant_no": ws.cell(row=r, column=3).value or "",
            "name": ws.cell(row=r, column=4).value or "",
            "birth": dates.date_to_ymd(birth) if birth else "",
            "koushu": koushu,
            "grade": ws.cell(row=r, column=2).value or "",
            "complete_date": dates.date_to_ymd(dates.to_date(ws.cell(row=r, column=8).value) or issue),
            "issue_date": dates.date_to_ymd(issue),
            "expiry": dates.date_to_ymd(dates.expiry_date(issue, MONTHS, MINUS)),
            "koushi": ws.cell(row=r, column=21).value or "",
            "gentei_map": {air: _split(col) for air, col in GENTEI_COLS.items()},
        })
        r += 1
    return out


# ============================================================
# 画面
# ============================================================
st.title("📄 帳票作成（修了者名簿・講習実施記録）")
st.caption(f"保存先: {REPORT_DIR}")

if not MASTER.exists():
    st.error(f"master.xlsx が見つかりません: {MASTER}")
    st.stop()
wb = load_workbook(MASTER)
if SHEET not in wb.sheetnames:
    st.error(f"「{SHEET}」シートがありません: {MASTER}")
    st.stop()

people = read_people(wb[SHEET])
if not people:
    st.warning("master.xlsx に修了者がいません。「masterに入力」ページで登録してください。")
    st.stop()

all_rows = reports.build_roster_rows(people)

# ---- 絞り込み ----
st.subheader("1. 対象期間")
dates_in_master = sorted({d for d in (reports.parse_date(r["complete_date"])
                                     for r in all_rows) if d})
lo = dates_in_master[0] if dates_in_master else dt.date.today()
hi = dates_in_master[-1] if dates_in_master else dt.date.today()

c1, c2, c3 = st.columns([1, 1, 2])
use_all = c3.checkbox("全期間を対象にする", value=True)
start = c1.date_input("開始日（修了日）", value=lo, format="YYYY/MM/DD", disabled=use_all)
end = c2.date_input("終了日（修了日）", value=hi, format="YYYY/MM/DD", disabled=use_all)

if use_all:
    rows = all_rows
    period = "全期間"
    suffix = "全期間"
else:
    if start > end:
        st.error("開始日が終了日より後になっています。")
        st.stop()
    rows = reports.filter_by_period(all_rows, start, end)
    period = f"{start:%Y/%m/%d}〜{end:%Y/%m/%d}"
    suffix = f"{start:%Y%m%d}-{end:%Y%m%d}"

kubun = st.multiselect("講習区分で絞り込む（未選択は全区分）",
                       sorted({r["koushu"] for r in all_rows}))
if kubun:
    rows = reports.renumber([r for r in rows if r["koushu"] in kubun])

if not rows:
    st.warning("条件に一致する修了者がいません。期間や講習区分を見直してください。")
    st.stop()

records = reports.build_record_rows(rows)
st.success(f"対象 {len(rows)} 名 / 講習実施 {len(records)} 回")

# ---- プレビュー ----
st.subheader("2. プレビュー")
tab1, tab2 = st.tabs(["修了者名簿", "講習実施記録"])
with tab1:
    st.dataframe(pd.DataFrame([{label: r.get(key, "") for label, key, _, _
                                in reports.ROSTER_COLUMNS} for r in rows]),
                 hide_index=True, use_container_width=True)
with tab2:
    st.dataframe(pd.DataFrame([{label: r.get(key, "") for label, key, _, _
                                in reports.RECORD_COLUMNS} for r in records]),
                 hide_index=True, use_container_width=True)

# ---- 生成 ----
st.subheader("3. 帳票を作成")
kind = st.radio("帳票の種類", ["修了者名簿", "講習実施記録"], horizontal=True)
fmt = st.radio("形式", ["PDF", "Excel"], horizontal=True)

if st.button("📄 帳票を作成", type="primary"):
    is_roster = kind == "修了者名簿"
    data = rows if is_roster else records
    ext = "pdf" if fmt == "PDF" else "xlsx"
    out = REPORT_DIR / f"{kind}_{suffix}.{ext}"
    try:
        if is_roster:
            fn = reports.roster_pdf if fmt == "PDF" else reports.roster_xlsx
        else:
            fn = reports.record_pdf if fmt == "PDF" else reports.record_xlsx
        fn(data, out, org, period=period)
    except Exception as e:  # noqa: BLE001
        st.error(f"帳票の作成に失敗しました: {e}")
        st.stop()

    st.success(f"{kind}（{fmt}）を作成しました: {out}")
    mime = ("application/pdf" if fmt == "PDF"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with open(out, "rb") as f:
        st.download_button(f"⬇️ {out.name} をダウンロード", f.read(),
                           file_name=out.name, mime=mime)
