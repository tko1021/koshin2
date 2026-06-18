# -*- coding: utf-8 -*-
"""DIPS登録用CSV（公式17列）を作成・ダウンロード。発行履歴はGoogleシートに記録。"""
import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

import _common
from dips import auth, dates, pipeline, store

st.set_page_config(page_title="DIPS_CSV作成", layout="wide")
auth.require_login()

today = dt.date.today()
st.title("📤 DIPS登録用CSVを作成")

people = _common.enrich(store.read_people())
if not people:
    st.info("登録がありません。「修了者を登録」ページから追加してください。")
    st.stop()

records = [_common.to_record(e) for e in people]
history = store.read_history()
issued = {str(h.get("申請ID") or "") for h in history if h.get("申請ID")}
new_cnt = sum(1 for e in people if e["_cert"] not in issued)

st.dataframe(pd.DataFrame([{"証明書番号": e["_cert"], "氏名": e["氏名"], "状態": e.get("状態", ""),
                           "修了日": dates.date_to_ymd(e["_comp"]),
                           "発行済み": "○" if e["_cert"] in issued else ""} for e in people]),
             hide_index=True, use_container_width=True)
st.write(f"未発行：**{new_cnt} 件**　／　発行済み（自動除外）：{len(people) - new_cnt} 件")
st.caption("発行済みの申請IDは履歴で自動除外されます。何度押しても未発行分だけが出ます。")

if st.button("📤 DIPS登録用CSV を発行", type="primary", disabled=(new_cnt == 0)):
    tmp_settings, paths = _common.temp_paths()
    prepared = pipeline.prepare_rows(records, _common.ORG, _common.code_map, _common.mapping,
                                     tmp_settings, history_rows=history, today=today)
    now = dt.datetime.now()  # noqa: DTZ005 表示用
    report = pipeline.generate(prepared, tmp_settings, paths, _common.mapping,
                               date_str=today.strftime("%Y%m%d"),
                               now_str=now.strftime("%Y-%m-%d %H:%M:%S"), write_log=False)

    st.success(f"CSV生成：{report.total_written} 件 / {len(report.files)} ファイル")
    hist_entries = []
    for fr in report.files:
        fname = Path(fr.path).name
        with open(fr.path, "rb") as f:
            data = f.read()
        passed = "✅ 合格" if fr.selftest.passed else "❌ 不合格"
        st.markdown(f"**{fname}**（{fr.count}件）　セルフテスト: {passed}")
        st.table(pd.DataFrame([{"項目": c.name, "結果": "OK" if c.ok else "NG"}
                               for c in fr.selftest.checks]))
        st.download_button(f"⬇️ {fname} をダウンロード", data, file_name=fname, mime="text/csv")
        for pr in fr.rows:
            rec = pr.record
            hist_entries.append({
                "日時": now.strftime("%Y-%m-%d %H:%M:%S"),
                "氏名": rec.get("氏名", ""), "申請ID": pr.apply_id,
                "修了証明書番号": pr.shumeisho, "状態フラグ": pr.status_flag, "ファイル名": fname})
    if hist_entries:
        store.append_history(hist_entries)
        st.caption("発行履歴をGoogleシートに記録しました。")

    if report.excluded:
        st.warning("以下は検証エラー等で除外されました：")
        for pr in report.excluded:
            reasons = list(pr.integrity_errors) + ([pr.block_reason] if pr.blocked else [])
            st.write(f"- {pr.apply_id}: {' / '.join(r for r in reasons if r)}")
