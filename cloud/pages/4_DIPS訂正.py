# -*- coding: utf-8 -*-
"""DIPS登録済みの訂正（上書き修正・無効化）。訂正用CSVを作成・ダウンロード。"""
import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

import _common
from dips import auth, dates, pipeline, store

st.set_page_config(page_title="DIPS訂正", layout="wide")
auth.require_login()

today = dt.date.today()
st.title("🔧 DIPS登録済みの訂正（上書き修正・無効化）")

people = _common.enrich(store.read_people())
history = store.read_history()
issued_ids = {str(h.get("申請ID") or "") for h in history if h.get("申請ID")}
issued = [e for e in people if e["_cert"] in issued_ids]

if not issued:
    st.info("発行済みの修了者がいません。先に「DIPS_CSV作成」で発行してください。")
    st.stop()

st.dataframe(pd.DataFrame([{"証明書番号(申請ID)": e["_cert"], "氏名": e["氏名"],
                           "発行日": e.get("証明書発行日", "")} for e in issued]),
             hide_index=True, use_container_width=True)

labels = {f'{e["氏名"]}（{e["_cert"]}）': i for i, e in enumerate(issued)}
sel = st.selectbox("訂正する修了者", list(labels.keys()))
e = issued[labels[sel]]

st.info("内容を直す場合は、先に「一覧・編集」ページで修正してください"
        "（講習区分・発行日を変えなければ証明書番号＝申請IDは同じままです）。")
mode = st.radio("訂正の種類", ["上書き修正（内容を直して再登録）", "無効化（登録を取り消す）"])


def issue_correction(jotai, allow_invalidate):
    rec = _common.to_record(e, jotai_override=jotai)
    if rec["修了証明書番号(自動)"] != e["_cert"]:
        st.error(f"証明書番号が一致しません（{e['_cert']} ≠ {rec['修了証明書番号(自動)']}）。")
        return
    tmp_settings, paths = _common.temp_paths()
    prepared = pipeline.prepare_rows([rec], _common.ORG, _common.code_map, _common.mapping,
                                     tmp_settings, history_rows=history, today=today,
                                     allow_invalidate=allow_invalidate)
    now = dt.datetime.now()  # noqa: DTZ005
    report = pipeline.generate(prepared, tmp_settings, paths, _common.mapping,
                               date_str=today.strftime("%Y%m%d"),
                               now_str=now.strftime("%Y-%m-%d %H:%M:%S"), write_log=False)
    if not report.total_written:
        st.warning("発行できませんでした：")
        for pr in report.excluded:
            reasons = list(pr.integrity_errors) + ([pr.block_reason] if pr.blocked else [])
            st.write(f"- {' / '.join(r for r in reasons if r)}")
        return
    fr = report.files[0]
    fname = Path(fr.path).name
    st.success(f"訂正CSVを発行しました（セルフテスト: "
               f"{'✅合格' if fr.selftest.passed else '❌不合格'}）")
    st.download_button("⬇️ 訂正CSVをダウンロード", Path(fr.path).read_bytes(),
                       file_name=fname, mime="text/csv")
    store.append_history([{
        "日時": now.strftime("%Y-%m-%d %H:%M:%S"), "氏名": e.get("氏名", ""),
        "申請ID": e["_cert"], "修了証明書番号": e["_cert"],
        "状態フラグ": "2" if jotai.startswith("2") else "3", "ファイル名": fname}])


if mode.startswith("上書き修正"):
    if st.button("🔧 上書き修正CSVを発行", type="primary"):
        issue_correction("2：上書き修正", allow_invalidate=False)
else:
    st.warning("無効化すると、この修了者のDIPS登録が取り消されます。")
    if st.checkbox(f"「{e['氏名']}（{e['_cert']}）」を無効化することを確認しました"):
        if st.button("🗑 無効化CSVを発行", type="primary"):
            issue_correction("3：無効化", allow_invalidate=True)
