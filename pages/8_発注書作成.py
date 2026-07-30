# -*- coding: utf-8 -*-
"""発注書（A4縦PDF）を作成するページ。

- 発注先・件名・取引条件・明細を入力し、税率別に集計してPDFを生成
- 発注番号は発注日ごとに自動採番（保存先の既存PDFを見て次の連番）
- 保存先: 共有フォルダ（data_dir）の「発注書」フォルダ
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

from dips import certificate, config, order

st.set_page_config(page_title="発注書作成", layout="wide")

settings, mapping, code_map, paths = config.load_all()
ORDER_CFG = settings.get("order", {}) or {}
ORDER_DIR = Path(paths.data_dir) / "発注書"
UNITS = ORDER_CFG.get("units") or ["式", "個", "台", "本", "枚", "人", "時間", "日"]
TAX_RATES = [10, 8, 0]
PO_PATTERN = ORDER_CFG.get("po_no_pattern", "PO-{date}-{seq:02d}")
DEFAULT_RATE = int(ORDER_CFG.get("tax_rate", 10))
EMPTY_ROW = {"品名・仕様": "", "数量": 1.0, "単位": "式", "単価": 0, "税率(%)": DEFAULT_RATE}

st.title("🧾 発注書作成（PDF）")
st.caption(f"保存先: {ORDER_DIR}")

issuer_def = order.issuer_defaults(settings)
seal = certificate.find_seal(paths.data_dir)
if seal:
    st.caption(f"角印（印影）を押印します: {seal.name}")
else:
    st.caption(f"印影が未設置のため押印なしで出力します。"
               f"　押印するには `{Path(paths.data_dir) / '印影.png'}` を置いてください。")

# ============================================================
# 1. 発注先・発注情報
# ============================================================
st.subheader("1. 発注先・発注情報")
c1, c2, c3 = st.columns([2, 1, 1])
supplier = c1.text_input("発注先（会社名）", placeholder="株式会社○○")
honorific = c2.selectbox("敬称", ["御中", "様"])
issue_date = c3.date_input("発注日", value=dt.date.today(), format="YYYY/MM/DD")

c4, c5 = st.columns([2, 1])
subject = c4.text_input("件名", placeholder="ドローン講習用 機材一式")
po_no = c5.text_input("発注番号", value=order.next_po_no(ORDER_DIR, issue_date, PO_PATTERN))

# ============================================================
# 2. 取引条件
# ============================================================
st.subheader("2. 取引条件")
c6, c7, c8 = st.columns(3)
use_date = c6.checkbox("納期を日付で指定", value=True)
delivery_date = c6.date_input("納期", value=issue_date + dt.timedelta(days=30),
                              format="YYYY/MM/DD", disabled=not use_date)
delivery_text = c6.text_input("納期（文章で指定する場合）", placeholder="別途協議",
                              disabled=use_date)
delivery_place = c7.text_input("納品場所", value=ORDER_CFG.get("delivery_place", ""))
payment_terms = c8.text_input("支払条件",
                              value=ORDER_CFG.get("payment_terms", "月末締め翌月末払い"))

# ============================================================
# 3. 明細
# ============================================================
st.subheader("3. 明細")
st.caption("行を追加して入力してください。金額＝数量×単価（円未満四捨五入）。"
           "消費税は税率ごとに1回だけ切り捨てで計算します。")

edited = st.data_editor(
    pd.DataFrame([EMPTY_ROW]), num_rows="dynamic", use_container_width=True,
    key="order_items",
    column_config={
        "品名・仕様": st.column_config.TextColumn(width="large"),
        "数量": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.2f"),
        "単位": st.column_config.SelectboxColumn(options=UNITS),
        "単価": st.column_config.NumberColumn(min_value=0, step=1000, format="%d"),
        "税率(%)": st.column_config.SelectboxColumn(options=TAX_RATES),
    })

items = [{"name": r["品名・仕様"], "qty": r["数量"], "unit": r["単位"],
          "price": r["単価"], "tax_rate": r["税率(%)"] if r["税率(%)"] is not None
          else DEFAULT_RATE}
         for _, r in edited.iterrows() if str(r["品名・仕様"] or "").strip()]

if not items:
    st.info("品名を1行以上入力すると、合計金額と発注書の作成ボタンが表示されます。")
    st.stop()

totals = order.compute_totals(items)
st.dataframe(pd.DataFrame([{"No": i, "品名・仕様": ln["name"], "数量": ln["qty"],
                            "単位": ln["unit"], "単価": order.yen(ln["price"]),
                            "金額": order.yen(ln["amount"]), "税率": f'{ln["tax_rate"]}%'}
                           for i, ln in enumerate(totals["lines"], start=1)]),
             hide_index=True, use_container_width=True)

m1, m2, m3 = st.columns(3)
m1.metric("小計（税抜）", order.yen(totals["subtotal"]))
m2.metric("消費税", order.yen(totals["tax"]))
m3.metric("合計（税込）", order.yen(totals["total"]))
if len(totals["by_rate"]) > 1:
    st.caption("税率別： " + " ／ ".join(
        f'{rate}% → 対象 {order.yen(v["subtotal"])}・税 {order.yen(v["tax"])}'
        for rate, v in totals["by_rate"].items()))

# ============================================================
# 4. 発注者・備考
# ============================================================
st.subheader("4. 発注者（自社）・備考")
st.caption("既定値は config/settings.yaml の `order:` / `organization:` から読み込みます。")
c9, c10 = st.columns(2)
issuer_name = c9.text_input("会社名", value=issuer_def["name"])
issuer_address = c9.text_input("住所", value=issuer_def["address"])
c11, c12, c13 = st.columns(3)
tel = c11.text_input("TEL", value=issuer_def["tel"])
fax = c12.text_input("FAX", value=issuer_def["fax"])
person = c13.text_input("発注担当者", value=issuer_def["person"])
note = c10.text_area("備考", height=132)

# ============================================================
# 5. 作成
# ============================================================
st.subheader("5. 発注書を作成")
if st.button("🧾 発注書を作成（PDF）", type="primary"):
    if not supplier.strip():
        st.error("発注先を入力してください。")
        st.stop()

    data = {
        "po_no": po_no, "issue_date": issue_date,
        "supplier": supplier, "honorific": honorific, "subject": subject,
        "delivery_date": delivery_date if use_date else None,
        "delivery_date_text": "" if use_date else delivery_text,
        "delivery_place": delivery_place, "payment_terms": payment_terms,
        "note": note, "items": items,
        "issuer": {"name": issuer_name, "address": issuer_address,
                   "tel": tel, "fax": fax, "person": person},
    }
    safe = "".join(ch for ch in supplier if ch not in '\\/:*?"<>|').strip()
    out = ORDER_DIR / f"{po_no}_{safe}.pdf"
    try:
        order.generate_order(data, out, seal_image=seal)
    except Exception as e:  # noqa: BLE001
        st.error(f"発注書の作成に失敗しました: {e}")
        st.stop()

    st.success(f"発注書を作成しました: {out}")
    with open(out, "rb") as f:
        st.download_button("⬇️ 発注書PDFをダウンロード", f.read(),
                           file_name=out.name, mime="application/pdf")
