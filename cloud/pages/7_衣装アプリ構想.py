# -*- coding: utf-8 -*-
"""衣装アプリ構想：新規事業アイデアを構造化して検証する。

内容は config/portfolio.yaml の costume_app を編集すると更新されます。
"""
import streamlit as st

from dips import auth, portfolio

st.set_page_config(page_title="衣装アプリ構想", layout="wide")
auth.require_login()

pf = portfolio.load_portfolio()
app = pf.get("costume_app", {}) or {}

st.title("👗 衣装アプリ構想")
if app.get("headline"):
    st.subheader(app["headline"])
if app.get("one_liner"):
    st.info(app["one_liner"])


def _section(title: str, items, icon: str = ""):
    items = items or []
    if not items:
        return
    st.markdown(f"### {icon} {title}")
    for it in items:
        st.markdown(f"- {it}")


c1, c2 = st.columns(2)
with c1:
    _section("解決したい課題", app.get("problem"), "🎯")
    _section("ターゲット", app.get("target"), "👥")
    _section("提供価値", app.get("value"), "✨")
with c2:
    _section("マネタイズ", app.get("monetization"), "💰")
    _section("MVP（最小で検証する範囲）", app.get("mvp"), "🚀")
    _section("既存事業との相乗効果", app.get("synergy"), "🔗")

_section("リスクと対策", app.get("risks"), "⚠️")

st.divider()
# ポートフォリオ上の位置づけ（ダッシュボードのスコアと連動）
costume = next((v for v in portfolio.scored_ventures(pf)
                if v.get("id") == "costume_app"), None)
if costume:
    st.markdown("#### ポートフォリオ上の位置づけ")
    m = st.columns(4)
    m[0].metric("魅力度", costume["_attractiveness"])
    m[1].metric("実現性", costume["_feasibility"])
    m[2].metric("優先度", costume["_priority"])
    m[3].metric("象限", costume["_quadrant"])
    st.caption("スコアは代表ダッシュボードのマトリクスと連動しています"
               "（config/portfolio.yaml で編集）。")

st.caption("この構想は config/portfolio.yaml の costume_app を編集すると更新されます。")
