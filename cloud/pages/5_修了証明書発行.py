# -*- coding: utf-8 -*-
"""修了証明書PDFを発行・ダウンロード（公式様式1・印影同梱）。"""
import datetime as dt
import io
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

import _common
from dips import auth, certificate, store

st.set_page_config(page_title="修了証明書発行", layout="wide")
auth.require_login()

ASSETS = Path(_common.__file__).resolve().parent.parent / "assets"
SEAL = _common.get_seal_path()   # クラウドはSecrets、ローカルはassets/印影.png
TEMPLATE = next((ASSETS / n for n in ["修了証明書テンプレート.png"]
                 if (ASSETS / n).exists()), None)

st.title("📜 修了証明書 発行（PDF）")
st.caption("公式様式1。担当講師・限定解除は登録内容を使用。"
           + (f"印影：{SEAL.name}" if SEAL else "印影未設定（「印」枠表示）"))

people = _common.enrich(store.read_people())
if not people:
    st.info("登録がありません。「修了者を登録」ページから追加してください。")
    st.stop()


def _gentei_sum(gmap, grade=""):
    # 表示ロジックはPDF（certificate.display_gentei）と共通。マルチのみ・「・」で1行連結。
    return "・".join(certificate.display_gentei(gmap, grade))


view = []
for e in people:
    d = _common.to_cert_data(e)
    view.append({"証明書番号": d["cert_no"], "氏名": d["name"], "資格区分": d["grade"],
                 "担当講師": d["koushi"], "限定解除": _gentei_sum(d["gentei_map"], d["grade"])})
st.dataframe(pd.DataFrame(view), hide_index=True, use_container_width=True)

labels = ["▼ 全員分を一括発行"] + [f'{e["氏名"]}（{e["_cert"]}）' for e in people]
sel = st.selectbox("発行する対象", labels)


def make_pdf(e, outdir):
    data = _common.to_cert_data(e)
    safe = str(e.get("氏名", "")).replace("　", "").replace(" ", "").replace("/", "_")
    out = Path(outdir) / f"{data['cert_no']}_{safe}.pdf"
    certificate.generate_certificate(data, out, template_image=TEMPLATE, seal_image=SEAL)
    return out


if st.button("📜 修了証明書を発行（PDF）", type="primary"):
    targets = people if sel.startswith("▼") else [people[labels.index(sel) - 1]]
    outdir = tempfile.mkdtemp(prefix="koshin_cert_")
    made = [make_pdf(e, outdir) for e in targets]
    st.success(f"{len(made)} 件発行しました。")
    if len(made) == 1:
        st.download_button("⬇️ PDFをダウンロード", made[0].read_bytes(),
                           file_name=made[0].name, mime="application/pdf")
    else:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in made:
                z.write(p, arcname=p.name)
        st.download_button("⬇️ 全員分をZIPでダウンロード", buf.getvalue(),
                           file_name=f"修了証明書_{dt.date.today():%Y%m%d}.zip",
                           mime="application/zip")
        for p in made:
            st.write(f"- {p.name}")
