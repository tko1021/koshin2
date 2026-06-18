"""手入力で「修了証明書発行台帳」(Googleスプレッドシート)へ記録し、
DIPS更新修了者情報CSVを発行するページ（Streamlit マルチページ）。

- 台帳の保存先: Googleスプレッドシート（サービスアカウント認証 / open_by_key）
- DIPS CSV: settings.yaml の data_dir 配下（従来どおり）
- 修了証明書番号は固有番号4桁だけ入力 → UC+機関コード+発行年月+固有 を自動組立
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from dips import config, export_log, intake, pipeline, sheets

st.set_page_config(page_title="手入力で発行", layout="wide")

settings, mapping, code_map, paths = config.load_all()
org = settings.get("organization", {})
sheet_id = config.get_sheet_id(settings)
ws_title = (settings.get("sheets") or {}).get("worksheet", "修了証明書発行台帳")
today = dt.date.today()

st.title("✍️ 手入力で台帳記録 ＆ DIPS CSV発行")
st.caption(
    f"台帳シートID: {sheet_id or '(未設定: 環境変数 KOSHIN_SHEET_ID か settings.yaml)'}　|　"
    f"CSV保存先: {paths.data_dir}　|　機関コード: {org.get('kikan_code', '(未設定)')}"
)

if "pending" not in st.session_state:
    st.session_state.pending = []

# ---- 入力フォーム ----
with st.form("entry", clear_on_submit=True):
    st.subheader("修了者を入力")
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("氏名 *")
    birth_date = c2.date_input("生年月日", value=None, format="YYYY/MM/DD",
                               min_value=dt.date(1925, 1, 1), max_value=today)
    kubun = c3.selectbox("区分 *", ["一等", "二等"])

    c4, c5, c6 = st.columns(3)
    applicant_no = c4.text_input("技能証明申請者番号 *（10文字以内）", max_chars=10)
    complete_date = c5.date_input("修了日 *", value=today, format="YYYY/MM/DD")
    issue_date = c6.date_input("修了証明書発行日 *", value=today, format="YYYY/MM/DD")

    c7, c8, c9 = st.columns(3)
    serial = c7.number_input("固有番号 *（月内連番 1〜9999）", min_value=1, max_value=9999,
                             value=1, step=1)
    prefix_label = c8.selectbox("講習区分", ["UC（更新講習）", "EL（失効再交付講習）"], index=0)
    prefix = prefix_label[:2]
    koushi = c9.text_input("担当講師")

    c10, c11, c12 = st.columns(3)
    genteikaijo = c10.text_input("限定解除事項")
    koufu = c11.selectbox("交付の有無", ["有", "無"], index=0)
    reissue_date = c12.date_input("再交付年月日（再交付時のみ）", value=None, format="YYYY/MM/DD")

    st.markdown("**DIPS連携用**")
    c13, c14, c15 = st.columns(3)
    teishi = c13.selectbox("停止処分者向け講習受講", ["無", "有"], index=0)
    jotai = c14.selectbox("登録種別", ["1：新規", "2：上書き修正", "3：無効化"], index=0)
    office = c15.text_input("事務所コード", value=org.get("office_code_default", ""))

    biko = st.text_input("備考")

    preview_no = intake.build_shumeisho_no(prefix, org.get("kikan_code", ""), issue_date, serial)
    st.info(f"自動組立される修了証明書番号: **{preview_no}**")

    submitted = st.form_submit_button("➕ 一覧に追加", type="primary")

if submitted:
    if not name or not applicant_no:
        st.error("氏名と技能証明申請者番号は必須です。")
    else:
        form = {
            "name": name, "birth_date": birth_date, "kubun": kubun,
            "applicant_no": applicant_no, "complete_date": complete_date,
            "issue_date": issue_date, "serial": int(serial), "prefix": prefix,
            "koushi": koushi, "genteikaijo": genteikaijo, "koufu": koufu,
            "reissue_date": reissue_date, "teishi": teishi, "jotai": jotai,
            "office_code": office, "biko": biko,
        }
        dips_rec = intake.compute_row(
            form, org, holidays=[],
            months=settings["validity"]["months"],
            minus_days=settings["validity"]["minus_days"],
            link_due_days=settings["business_days"]["link_due_days"])
        ledger = intake.build_ledger_row(
            form, org,
            months=settings["validity"]["months"],
            minus_days=settings["validity"]["minus_days"])
        st.session_state.pending.append({"dips": dips_rec, "ledger": ledger})
        st.success(f"追加しました: {name}（{ledger['修了証明書番号']}）")

# ---- 発行待ち一覧 ----
st.divider()
st.subheader(f"発行待ち一覧（{len(st.session_state.pending)} 件）")

if not st.session_state.pending:
    st.write("まだ追加されていません。上のフォームから入力してください。")
else:
    st.dataframe(pd.DataFrame([p["ledger"] for p in st.session_state.pending]),
                 hide_index=True, use_container_width=True)

    col_a, col_b = st.columns([1, 2])
    if col_a.button("🗑 一覧をクリア"):
        st.session_state.pending = []
        st.rerun()

    if col_b.button("✅ 台帳に記録して CSV を発行", type="primary"):
        ledger_rows = [p["ledger"] for p in st.session_state.pending]
        dips_records = [p["dips"] for p in st.session_state.pending]

        # 1) 台帳スプレッドシートへ追記（失敗時はCSVを出さず中断）
        try:
            n = sheets.append_ledger_rows(ledger_rows, sheet_id=sheet_id, worksheet=ws_title)
            st.success(f"台帳シートに {n} 件を追記しました。")
        except Exception as e:  # noqa: BLE001
            st.error("台帳シートへの追記に失敗しました（CSVは発行していません）。"
                     "鍵の配置・KOSHIN_SHEET_ID・シートの共有設定を確認してください。")
            st.exception(e)
            st.stop()

        # 2) DIPS CSV発行
        history = export_log.read_log(paths.export_log)
        prepared = pipeline.prepare_rows(
            dips_records, org, code_map, mapping, settings,
            history_rows=history, today=today)
        date_str = today.strftime("%Y%m%d")
        now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = pipeline.generate(prepared, settings, paths, mapping,
                                   date_str=date_str, now_str=now_str, write_log=True)

        st.success(f"CSV生成: {report.total_written} 件 / {len(report.files)} ファイル")
        for fr in report.files:
            passed = "✅ 合格" if fr.selftest.passed else "❌ 不合格"
            st.markdown(f"**{fr.path}**（{fr.count}件）　セルフテスト: {passed}")
            st.table(pd.DataFrame([{"項目": c.name, "結果": "OK" if c.ok else "NG", "詳細": c.detail}
                                   for c in fr.selftest.checks]))

        if report.excluded:
            st.error("以下はDIPS検証エラーでCSVから除外されました（台帳には記録済み）:")
            rows_err = []
            for pr in report.excluded:
                reasons = list(pr.integrity_errors)
                for e in pr.field_errors:
                    reasons.append(f"[列{e.index} {e.name}] {e.msg}")
                rows_err.append({"申請ID": pr.apply_id, "理由": " / ".join(reasons)})
            st.table(pd.DataFrame(rows_err))
        else:
            st.session_state.pending = []
            st.balloons()
