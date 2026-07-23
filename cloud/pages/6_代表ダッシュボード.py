# -*- coding: utf-8 -*-
"""代表ダッシュボード：現状・事業ポートフォリオ・選択と集中を一枚で把握する。

- ビジョン
- 現状KPI（既存事業のライブ値：登録修了者数 / DIPS連携期限の状況）
- 選択と集中マトリクス（魅力度 × 実現性）
- 事業カード（優先度順・次アクション）
"""
import datetime as dt

import pandas as pd
import streamlit as st

import _common
from dips import auth, dates, portfolio, store

st.set_page_config(page_title="代表ダッシュボード", layout="wide")
auth.require_login()

st.title("📊 代表ダッシュボード")
st.caption("既存事業・新規構想・メモを一枚に。選択と集中で意思決定する。")

pf = portfolio.load_portfolio()

# ---------- ビジョン ----------
if pf.get("vision"):
    st.info(pf["vision"])

# ---------- 現状KPI（既存事業のライブ値） ----------
st.subheader("現状（既存事業のライブ値）")


def _live_kpis():
    """Googleシートから既存事業の現状値を計算。接続不可なら None。"""
    people = _common.enrich(store.read_people())
    today = dt.date.today()
    overdue = due_soon = 0
    for e in people:
        # DIPS連携期限 = 発行日から5営業日（土日除外の近似。祝日は概算に含めない）
        deadline = dates.add_business_days(e["_issue"], _common.LINK_DUE, holidays=[])
        remain = (deadline - today).days
        if remain < 0:
            overdue += 1
        elif remain <= 2:
            due_soon += 1
    return {"people_count": len(people), "overdue_count": overdue,
            "due_soon_count": due_soon}


try:
    kpi = _live_kpis()
    c1, c2, c3 = st.columns(3)
    c1.metric("登録修了者", f'{kpi["people_count"]} 件')
    c2.metric("連携期限 超過", f'{kpi["overdue_count"]} 件',
              delta=None if kpi["overdue_count"] == 0 else "要対応",
              delta_color="inverse")
    c3.metric("連携期限 間近(2営業日内)", f'{kpi["due_soon_count"]} 件')
    st.caption("※ 期限は土日のみ除外の近似値。正確な一覧は「一覧・編集」ページで確認してください。")
except Exception as e:  # noqa: BLE001
    st.warning("既存事業のライブ値を取得できませんでした（Googleシート未接続でも他の機能は使えます）。")
    with st.expander("エラー詳細"):
        st.exception(e)

# ---------- 選択と集中マトリクス ----------
st.divider()
st.subheader("選択と集中マトリクス")
st.caption("縦=魅力度（市場性・収益性・ビジョン適合の平均） / "
           "横=実現性（自社の強み・リソース・着手容易性の平均）。円が大きいほど優先度が高い。")

ventures = portfolio.scored_ventures(pf)
threshold = float(pf.get("threshold", 3.0))

if not ventures:
    st.write("事業が未登録です。config/portfolio.yaml の ventures を編集してください。")
else:
    df = pd.DataFrame([{
        "事業": v.get("name", v.get("id", "")),
        "実現性": v["_feasibility"],
        "魅力度": v["_attractiveness"],
        "優先度": v["_priority"],
        "象限": v["_quadrant"],
        "アイコン": v.get("icon", ""),
    } for v in ventures])

    try:
        import altair as alt

        base = alt.Chart(df)
        points = base.mark_circle(opacity=0.85).encode(
            x=alt.X("実現性:Q", scale=alt.Scale(domain=[1, 5]),
                    title="実現性 →（やりやすい）"),
            y=alt.Y("魅力度:Q", scale=alt.Scale(domain=[1, 5]),
                    title="魅力度 →（やる価値）"),
            size=alt.Size("優先度:Q", scale=alt.Scale(range=[200, 2000]),
                          legend=None),
            color=alt.Color("象限:N", legend=alt.Legend(title="象限")),
            tooltip=["事業", "魅力度", "実現性", "優先度", "象限"],
        )
        labels = base.mark_text(dy=-18, fontSize=12).encode(
            x="実現性:Q", y="魅力度:Q", text="事業:N")
        vline = alt.Chart(pd.DataFrame({"x": [threshold]})).mark_rule(
            strokeDash=[4, 4], color="gray").encode(x="x:Q")
        hline = alt.Chart(pd.DataFrame({"y": [threshold]})).mark_rule(
            strokeDash=[4, 4], color="gray").encode(y="y:Q")
        chart = (vline + hline + points + labels).properties(height=420)
        st.altair_chart(chart, use_container_width=True)
    except Exception:  # noqa: BLE001 altair非対応環境のフォールバック
        st.scatter_chart(df, x="実現性", y="魅力度", size="優先度", color="象限")

# ---------- 事業カード（優先度順） ----------
st.divider()
st.subheader("事業ポートフォリオ（優先度順）")

QUAD_ICON = {
    "集中投資（本命）": "🟢",
    "育成・検証": "🟡",
    "効率運用": "🔵",
    "撤退・保留候補": "⚪",
}

for v in ventures:
    icon = v.get("icon", "")
    quad = v["_quadrant"]
    with st.container(border=True):
        top = st.columns([3, 1, 1, 1])
        top[0].markdown(f"### {icon} {v.get('name', '')}")
        top[0].caption(f"{v.get('stage', '')}　|　役割: {v.get('role', '')}")
        top[1].metric("魅力度", v["_attractiveness"])
        top[2].metric("実現性", v["_feasibility"])
        top[3].metric("優先度", v["_priority"])
        st.markdown(f"{QUAD_ICON.get(quad, '•')} **{quad}**")
        if v.get("summary"):
            st.write(v["summary"])
        actions = v.get("next_actions") or []
        if actions:
            st.markdown("**次アクション**")
            for a in actions:
                st.markdown(f"- {a}")

st.divider()
st.caption("スコアは config/portfolio.yaml で編集できます（1〜5の5段階）。"
           "根拠や気づきは「メモ」ページへ。")
