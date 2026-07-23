# -*- coding: utf-8 -*-
"""経営メモ：気づき・アイデア・現状を記録する（代表ダッシュボード用）。

Googleシート「経営メモ」タブに保存（新しい順に表示）。
シート未接続時はこのセッション内だけの一時メモにフォールバックする。
"""
import datetime as dt

import pandas as pd
import streamlit as st

from dips import auth, portfolio, store

st.set_page_config(page_title="メモ", layout="wide")
auth.require_login()

st.title("📝 経営メモ")
st.caption("現状・気づき・アイデアをここに集約。関連事業を紐づけると振り返りやすくなります。")

pf = portfolio.load_portfolio()
CATEGORIES = ["現状", "気づき", "アイデア", "課題", "決定事項", "その他"]
venture_names = [v.get("name", "") for v in pf.get("ventures", [])]
RELATED = ["（全体）"] + venture_names

# ---------- 入力 ----------
with st.form("memo", clear_on_submit=True):
    c1, c2 = st.columns(2)
    category = c1.selectbox("分類", CATEGORIES)
    related = c2.selectbox("関連事業", RELATED)
    body = st.text_area("内容", height=120, placeholder="例：更新講習の集客導線を衣装アプリの初期ユーザー獲得に使えないか")
    ok = st.form_submit_button("➕ メモを保存", type="primary")

if ok:
    if not body.strip():
        st.error("内容を入力してください。")
        st.stop()
    entry = {"日時": dt.datetime.now().strftime("%Y/%m/%d %H:%M"),
             "分類": category, "関連事業": related, "内容": body.strip()}
    try:
        store.append_memo(entry)
        st.success("保存しました。")
    except Exception as e:  # noqa: BLE001 シート未接続 → セッションに退避
        st.session_state.setdefault("_local_memos", []).insert(0, entry)
        st.warning("Googleシートに保存できなかったため、このセッション内に一時保存しました。")
        with st.expander("エラー詳細"):
            st.exception(e)
    st.rerun()

st.divider()

# ---------- 一覧 ----------
memos = []
sheet_ok = True
try:
    memos = store.read_memos()
except Exception:  # noqa: BLE001
    sheet_ok = False
memos = st.session_state.get("_local_memos", []) + memos

if not sheet_ok and not memos:
    st.info("Googleシート未接続です。保存はこのセッション内のみ有効になります。")

if not memos:
    st.write("まだメモがありません。")
    st.stop()

# 絞り込み
f1, f2 = st.columns(2)
fc = f1.multiselect("分類で絞り込み", CATEGORIES)
fr = f2.multiselect("関連事業で絞り込み", RELATED)
view = [m for m in memos
        if (not fc or m.get("分類") in fc) and (not fr or m.get("関連事業") in fr)]

st.caption(f"{len(view)} 件")
for m in view:
    with st.container(border=True):
        st.markdown(f"**{m.get('分類','')}**　`{m.get('関連事業','')}`　"
                    f"<span style='color:gray'>{m.get('日時','')}</span>",
                    unsafe_allow_html=True)
        st.write(m.get("内容", ""))

with st.expander("表形式で見る / コピー"):
    st.dataframe(pd.DataFrame(view), hide_index=True, use_container_width=True)
