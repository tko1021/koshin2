# -*- coding: utf-8 -*-
"""修了者を登録（Googleシートの修了者マスタへ追記）。"""
import datetime as dt

import streamlit as st

import _common
from dips import auth, certificate, dates, intake, store

st.set_page_config(page_title="修了者を登録", layout="wide")
auth.require_login()

today = dt.date.today()
st.title("📋 修了者を登録")

people = _common.enrich(store.read_people())


def preview_cert(koushu, issue):
    if not issue:
        return "", ""
    ym = f"{issue.year % 100:02d}{issue.month:02d}"
    same = sum(1 for e in people if e["_issue"].year % 100 == issue.year % 100
               and e["_issue"].month == issue.month)
    cert = intake.build_shumeisho_no(_common.PREFIX.get(koushu, "UC"),
                                     _common.KIKAN, issue, same + 1)
    expiry = dates.date_to_ymd(dates.expiry_date(issue, _common.MONTHS, _common.MINUS))
    return cert, expiry


with st.form("reg", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    koushu = c1.selectbox("講習区分 *", ["更新講習", "失効再交付講習"])
    grade = c2.selectbox("等級区分 *", ["一等", "二等"])
    appno = c3.text_input("技能証明申請者番号 *（10文字以内）", max_chars=10)

    c4, c5, c6 = st.columns(3)
    name = c4.text_input("氏名 *")
    birth = c5.date_input("生年月日", value=None, format="YYYY/MM/DD",
                          min_value=dt.date(1925, 1, 1), max_value=today)
    addr = c6.text_input("住所")

    c7, c8, c9 = st.columns(3)
    teishi = c7.selectbox("停止処分者向け講習 受講有無", ["無", "有"])
    comp = c8.date_input("修了日 *", value=today, format="YYYY/MM/DD")
    issue = c9.date_input("証明書発行日 *", value=today, format="YYYY/MM/DD")

    c10, c11 = st.columns(2)
    state = c10.selectbox("状態 *", ["新規", "上書き修正", "無効化"])
    phys = c11.text_input("身体適性検査証明書番号（空欄→PA000000000000）")

    st.markdown("**修了証明書用（任意）**")
    koushi = st.text_input("担当講師")
    g1, g2, g3 = st.columns(3)
    gentei = {
        "限定解除（回転翼マルチ）": g1.multiselect("回転翼（マルチ）", certificate.GENTEI_ITEMS),
        "限定解除（回転翼ヘリ）": g2.multiselect("回転翼（ヘリ）", certificate.GENTEI_ITEMS),
        "限定解除（飛行機）": g3.multiselect("飛行機", certificate.GENTEI_ITEMS),
    }

    pv_cert, pv_exp = preview_cert(koushu, issue)
    st.info(f"プレビュー　修了証明書番号: **{pv_cert}**　/　有効期限: **{pv_exp}**")
    ok = st.form_submit_button("➕ 登録する", type="primary")

if ok:
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
    try:
        store.append_person(values)
    except Exception as e:  # noqa: BLE001
        st.error("登録に失敗しました（シート接続/共有設定を確認）。")
        st.exception(e)
        st.stop()
    st.success(f"登録しました: {name}　{pv_cert}")
    st.rerun()

st.divider()
st.subheader(f"現在の登録（{len(people)} 件）")
if people:
    import pandas as pd
    st.dataframe(pd.DataFrame([{"証明書番号": e["_cert"], "氏名": e["氏名"],
                               "資格区分": e["等級区分"], "発行日": e["証明書発行日"],
                               "有効期限": dates.date_to_ymd(e["_expiry"])} for e in people]),
                 hide_index=True, use_container_width=True)
else:
    st.write("まだ登録がありません。")
