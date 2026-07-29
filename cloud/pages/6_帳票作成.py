# -*- coding: utf-8 -*-
"""帳票（修了者名簿・講習実施記録）を PDF / Excel で作成・ダウンロードする。"""
import datetime as dt
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

import _common
from dips import auth, reports, store

st.set_page_config(page_title="帳票作成", layout="wide")
auth.require_login()

ORG = _common.ORG
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

st.title("📄 帳票作成（修了者名簿・講習実施記録）")
st.caption("登録済みの修了者から名簿・実施記録を作成します。期間や講習区分で絞り込めます。")

people = _common.enrich(store.read_people())
if not people:
    st.info("登録がありません。「修了者を登録」ページから追加してください。")
    st.stop()

all_rows = reports.build_roster_rows([_common.to_roster_person(e) for e in people])

# ---- 絞り込み ----
st.subheader("1. 対象期間")
known = sorted({d for d in (reports.parse_date(r["complete_date"]) for r in all_rows) if d})
lo = known[0] if known else dt.date.today()
hi = known[-1] if known else dt.date.today()

c1, c2, c3 = st.columns([1, 1, 2])
use_all = c3.checkbox("全期間を対象にする", value=True)
start = c1.date_input("開始日（修了日）", value=lo, format="YYYY/MM/DD", disabled=use_all)
end = c2.date_input("終了日（修了日）", value=hi, format="YYYY/MM/DD", disabled=use_all)

if use_all:
    rows, period, suffix = all_rows, "全期間", "全期間"
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
    out = Path(tempfile.mkdtemp(prefix="koshin_report_")) / f"{kind}_{suffix}.{ext}"
    if is_roster:
        fn = reports.roster_pdf if fmt == "PDF" else reports.roster_xlsx
    else:
        fn = reports.record_pdf if fmt == "PDF" else reports.record_xlsx
    try:
        fn(data, out, ORG, period=period)
    except Exception as e:  # noqa: BLE001
        st.error(f"帳票の作成に失敗しました: {e}")
        st.stop()

    st.success(f"{kind}（{fmt}）を作成しました。")
    st.download_button(f"⬇️ {out.name} をダウンロード", out.read_bytes(),
                       file_name=out.name,
                       mime="application/pdf" if fmt == "PDF" else XLSX_MIME)
