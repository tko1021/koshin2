# -*- coding: utf-8 -*-
"""修了者の一覧・編集・削除（Googleシートの修了者マスタ）。"""
import datetime as dt

import pandas as pd
import streamlit as st

import _common
from dips import auth, certificate, dates, store

st.set_page_config(page_title="一覧・編集", layout="wide")
auth.require_login()

today = dt.date.today()
st.title("✏️ 修了者の一覧・編集・削除")

people = _common.enrich(store.read_people())
if not people:
    st.info("登録がありません。「修了者を登録」ページから追加してください。")
    st.stop()

st.dataframe(pd.DataFrame([{"証明書番号": e["_cert"], "氏名": e["氏名"], "資格区分": e["等級区分"],
                           "発行日": e["証明書発行日"], "有効期限": dates.date_to_ymd(e["_expiry"]),
                           "担当講師": e.get("担当講師", "")} for e in people]),
             hide_index=True, use_container_width=True)

labels = {f'{e["氏名"]}（{e["_cert"]}）': i for i, e in enumerate(people)}
sel = st.selectbox("編集・削除する修了者", list(labels.keys()))
e = people[labels[sel]]


def _d(key):
    return dates.to_date(e.get(key))


KOUSHU = ["更新講習", "失効再交付講習"]
GRADE = ["一等", "二等"]
TEISHI = ["無", "有"]
STATE = ["新規", "上書き修正", "無効化"]

st.divider()
with st.form("edit"):
    st.subheader("編集")
    c1, c2, c3 = st.columns(3)
    koushu = c1.selectbox("講習区分", KOUSHU, index=KOUSHU.index(e.get("講習区分", "更新講習")))
    grade = c2.selectbox("等級区分", GRADE, index=GRADE.index(e.get("等級区分", "一等")))
    appno = c3.text_input("技能証明申請者番号", value=e.get("技能証明申請者番号", ""), max_chars=10)
    c4, c5, c6 = st.columns(3)
    name = c4.text_input("氏名", value=e.get("氏名", ""))
    birth = c5.date_input("生年月日", value=_d("生年月日"), format="YYYY/MM/DD",
                          min_value=dt.date(1925, 1, 1), max_value=today)
    addr = c6.text_input("住所", value=e.get("住所", ""))
    c7, c8, c9 = st.columns(3)
    teishi = c7.selectbox("受講有無", TEISHI,
                          index=TEISHI.index(e.get("停止処分者向け講習受講有無") or "無"))
    comp = c8.date_input("修了日", value=_d("修了日") or today, format="YYYY/MM/DD")
    issue = c9.date_input("証明書発行日", value=_d("証明書発行日") or today, format="YYYY/MM/DD")
    c10, c11 = st.columns(2)
    state = c10.selectbox("状態", STATE, index=STATE.index(e.get("状態") or "新規"))
    phys = c11.text_input("身体適性検査証明書番号", value=e.get("身体適性検査証明書番号", ""))

    st.markdown("**修了証明書用**")
    koushi = st.text_input("担当講師", value=e.get("担当講師", ""))
    g1, g2, g3 = st.columns(3)
    gentei = {
        "限定解除（回転翼マルチ）": g1.multiselect(
            "回転翼（マルチ）", certificate.GENTEI_ITEMS,
            default=_common._split(e.get("限定解除（回転翼マルチ）"))),
        "限定解除（回転翼ヘリ）": g2.multiselect(
            "回転翼（ヘリ）", certificate.GENTEI_ITEMS,
            default=_common._split(e.get("限定解除（回転翼ヘリ）"))),
        "限定解除（飛行機）": g3.multiselect(
            "飛行機", certificate.GENTEI_ITEMS,
            default=_common._split(e.get("限定解除（飛行機）"))),
    }
    upd = st.form_submit_button("💾 更新", type="primary")

if upd:
    if not name or not appno:
        st.error("氏名と技能証明申請者番号は必須です。")
        st.stop()
    values = {
        "講習区分": koushu, "等級区分": grade, "技能証明申請者番号": appno, "氏名": name,
        "生年月日": dates.date_to_ymd(birth) if birth else "", "住所": addr,
        "停止処分者向け講習受講有無": teishi, "修了日": dates.date_to_ymd(comp),
        "証明書発行日": dates.date_to_ymd(issue), "状態": state,
        "身体適性検査証明書番号": phys, "担当講師": koushi,
        **{k: "、".join(v) for k, v in gentei.items()},
    }
    store.update_person(e["_row"], values)
    st.success(f"更新しました: {name}")
    st.rerun()

st.divider()
st.subheader("🗑 削除")
if st.checkbox(f"「{e['氏名']}（{e['_cert']}）」を削除する"):
    if st.button("🗑 削除実行"):
        store.delete_person(e["_row"])
        st.success("削除しました。")
        st.rerun()
