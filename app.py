"""DIPS 更新修了者情報CSV作成システム（Streamlit UI）。

完全ローカル動作・外部送信なし。
    起動: <venv>/Scripts/streamlit run app.py
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from dips import config, dates, excel_reader, export_log, pipeline
from dips.excel_reader import flatten_header

st.set_page_config(page_title="DIPS更新修了者CSV作成", layout="wide")

# はじめての方向け：操作マニュアルへのリンク（サイドバー先頭の「操作マニュアル」ページ）
st.page_link("pages/0_操作マニュアル.py", label="はじめての方はこちら → 操作マニュアル", icon="📖")


@st.cache_data(show_spinner=False)
def _load_config():
    return config.load_all()


def _load_master(master_path, _mapping):
    return excel_reader.read_master(master_path, _mapping)


def _fmt_date(value) -> str:
    d = dates.to_date(value)
    return dates.date_to_ymd(d) if d else ""


def _deadline_state(link_due, reg_status: str, today: dt.date) -> str:
    """連携期限の警告状態（赤/黄/空）。"""
    d = dates.to_date(link_due)
    if d is None or str(reg_status).strip() == "登録済":
        return ""
    if d < today:
        return "🔴超過"
    if (d - today).days <= 1:
        return "🟡間近"
    return ""


def build_dataframe(master, mapping, today: dt.date) -> pd.DataFrame:
    aux = mapping["master_aux"]
    cols = {
        "管理No": aux["kanri_no"], "氏名": aux["name"],
        "申請ID": "申請ID(自動=証明書番号)",
        "修了証明書番号": "修了証明書番号(自動)",
        "講習修了日": "講習修了日", "登録種別": "登録種別(状態フラグ)",
        "登録状況": aux["reg_status"], "DIPS連携期限": aux["link_due"],
    }
    rows = []
    for i, rec in enumerate(master.records):
        get = lambda key: rec.get(flatten_header(key))
        rows.append({
            "_idx": i,
            "選択": False,
            "管理No": get(cols["管理No"]),
            "氏名": get(cols["氏名"]),
            "区分": get("資格区分"),
            "講習修了日": _fmt_date(get(cols["講習修了日"])),
            "登録種別": get(cols["登録種別"]),
            "登録状況": get(cols["登録状況"]),
            "DIPS連携期限": _fmt_date(get(cols["DIPS連携期限"])),
            "期限": _deadline_state(get(cols["DIPS連携期限"]), get(cols["登録状況"]), today),
            "申請ID": get(cols["申請ID"]),
            "修了証明書番号": get(cols["修了証明書番号"]),
        })
    return pd.DataFrame(rows)


def main():
    st.title("DIPS 更新修了者情報CSV作成システム")
    settings, mapping, code_map, paths = _load_config()
    today = dt.date.today()

    # マスタ存在チェック
    if not paths.master.exists():
        st.error(f"master.xlsx が見つかりません: {paths.master}")
        st.stop()

    try:
        master = _load_master(str(paths.master), mapping)
    except Exception as e:  # noqa: BLE001
        st.exception(e)
        st.stop()

    # 設定シート未記入の警告
    sv = master.settings_values
    if sv.get("kikan_code", "") in ("", "0000") or "入力" in sv.get("kikan_name", ""):
        st.warning(
            f"⚠️ 設定シートが未記入の可能性: 機関コード={sv.get('kikan_code')!r} / "
            f"機関名={sv.get('kikan_name')!r} / 事務所コード既定={sv.get('office_code_default')!r}。"
            "実出力前にmaster.xlsxの「設定」シートへ実値を入力してください。"
        )

    st.caption(f"データフォルダ: {paths.data_dir}　|　修了者 {len(master.records)} 件　|　祝日 {len(master.holidays)} 件")

    tab_list, tab_history, tab_ops = st.tabs(["📋 一覧・生成", "🗂 出力履歴", "🔔 運用支援"])

    with tab_list:
        _tab_list(master, mapping, code_map, settings, paths, today)
    with tab_history:
        _tab_history(paths)
    with tab_ops:
        _tab_ops(master, mapping, today)


def _tab_list(master, mapping, code_map, settings, paths, today):
    df = build_dataframe(master, mapping, today)

    with st.expander("検索・フィルタ", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        name_q = c1.text_input("氏名で検索")
        shubetsu = c2.multiselect("登録種別", sorted(x for x in df["登録種別"].dropna().unique()))
        status = c3.multiselect("登録状況", sorted(x for x in df["登録状況"].dropna().unique()))
        only_warn = c4.checkbox("期限警告のみ")

    view = df.copy()
    if name_q:
        view = view[view["氏名"].astype(str).str.contains(name_q, na=False)]
    if shubetsu:
        view = view[view["登録種別"].isin(shubetsu)]
    if status:
        view = view[view["登録状況"].isin(status)]
    if only_warn:
        view = view[view["期限"] != ""]

    st.write(f"表示 {len(view)} / {len(df)} 件")
    edited = st.data_editor(
        view, hide_index=True, use_container_width=True,
        column_config={
            "_idx": None,
            "選択": st.column_config.CheckboxColumn("選択", default=False),
        },
        disabled=[c for c in view.columns if c not in ("選択",)],
        key="editor",
    )

    selected_idx = edited[edited["選択"]]["_idx"].tolist()
    st.write(f"選択中: {len(selected_idx)} 件")

    allow_inv = st.checkbox("無効化(状態フラグ3)の出力を許可する（要確認）", value=False)

    if st.button("✅ 選択行からCSVを生成", type="primary", disabled=not selected_idx):
        _do_generate(master, mapping, code_map, settings, paths, today,
                     selected_idx, allow_inv)


def _do_generate(master, mapping, code_map, settings, paths, today, selected_idx, allow_inv):
    records = [master.records[i] for i in selected_idx]
    history = export_log.read_log(paths.export_log)
    prepared = pipeline.prepare_rows(
        records, master.settings_values, code_map, mapping, settings,
        history_rows=history, today=today, allow_invalidate=allow_inv)

    # 「1：新規」再出力の警告
    applied = export_log.applied_new_ids(history)
    for pr in prepared:
        if pr.status_flag == "1" and pr.apply_id in applied:
            pr.warnings.append(f"申請ID {pr.apply_id} は既に「1：新規」で出力済みです")

    date_str = today.strftime("%Y%m%d")
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = pipeline.generate(prepared, settings, paths, mapping,
                               date_str=date_str, now_str=now_str, write_log=True)

    st.success(f"生成完了: {report.total_written} 件 / {len(report.files)} ファイル")
    for fr in report.files:
        passed = "✅ 合格" if fr.selftest.passed else "❌ 不合格"
        st.markdown(f"**{fr.path}**　（{fr.count}件）　セルフテスト: {passed}")
        st.table(pd.DataFrame([{"項目": c.name, "結果": "OK" if c.ok else "NG", "詳細": c.detail}
                               for c in fr.selftest.checks]))

    # 警告
    warns = [(pr.apply_id, w) for pr in prepared for w in pr.warnings]
    if warns:
        st.warning("警告:\n" + "\n".join(f"・{a}: {w}" for a, w in warns))

    # 除外行（エラーで出力対象外）
    if report.excluded:
        st.error("以下は出力から除外されました（行番号・項目・理由）:")
        rows = []
        for pr in report.excluded:
            reasons = list(pr.integrity_errors)
            if pr.block_reason:
                reasons.append(pr.block_reason)
            for e in pr.field_errors:
                reasons.append(f"[列{e.index} {e.name}] {e.msg}（値:{e.value}）")
            rows.append({"申請ID": pr.apply_id, "Excel行": pr.record.get("_row"),
                         "理由": " / ".join(reasons)})
        st.table(pd.DataFrame(rows))


def _tab_history(paths):
    history = export_log.read_log(paths.export_log)
    st.subheader("出力履歴 export_log.csv")
    if not history:
        st.info("履歴はまだありません。")
        return
    st.caption(str(paths.export_log))
    st.dataframe(pd.DataFrame(history), hide_index=True, use_container_width=True)


def _tab_ops(master, mapping, today):
    st.subheader("更新忘れ（未登録のまま連携期限を超過）")
    aux = mapping["master_aux"]
    rows = []
    for rec in master.records:
        get = lambda key: rec.get(flatten_header(key))
        status = str(get(aux["reg_status"]) or "").strip()
        due = dates.to_date(get(aux["link_due"]))
        if status != "登録済" and due is not None and due < today:
            rows.append({
                "管理No": get(aux["kanri_no"]), "氏名": get(aux["name"]),
                "DIPS連携期限": dates.date_to_ymd(due),
                "超過日数": (today - due).days, "登録状況": status or "(未設定)",
            })
    if rows:
        st.error(f"{len(rows)} 件が未登録のまま期限超過しています。")
        st.dataframe(pd.DataFrame(rows).sort_values("超過日数", ascending=False),
                     hide_index=True, use_container_width=True)
    else:
        st.success("期限超過の未登録はありません。")

    st.divider()
    st.subheader("DIPSエラー結果ファイルの取込（任意）")
    up = st.file_uploader("DIPSが出力したエラー結果CSVをアップロード", type=["csv"])
    if up is not None:
        raw = up.getvalue()
        text = raw.decode("utf-8-sig", errors="replace")
        st.text_area("内容プレビュー", text[:5000], height=240)


if __name__ == "__main__":
    main()
