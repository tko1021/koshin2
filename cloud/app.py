# -*- coding: utf-8 -*-
"""DIPS更新修了者 管理アプリ（クラウド版）ホーム。

データはGoogleスプレッドシート、認証はパスワード（Streamlit Secrets）。
"""
import streamlit as st

import _common  # noqa: F401  sys.path 設定（dips を import 可能に）
from dips import auth, store

st.set_page_config(page_title="DIPS更新修了者 管理", layout="wide")
auth.require_login()

st.title("🛩 DIPS更新修了者 管理アプリ（クラウド版）")
st.caption(f"機関コード: {_common.KIKAN}　|　{_common.ORG.get('kikan_name','')}")

try:
    st.page_link("pages/0_操作マニュアル.py", label="はじめての方はこちら → 操作マニュアル", icon="📖")
except Exception:  # noqa: BLE001 古いStreamlit
    pass

st.markdown(
    """
左のサイドバーから操作してください。

| ページ | 用途 |
|---|---|
| **修了者を登録** | 修了者を新しく登録（担当講師・限定解除も） |
| **一覧・編集** | 登録内容の確認・修正・削除 |
| **DIPS_CSV作成** | DIPS登録用CSV（公式17列）を作成・ダウンロード |
| **DIPS訂正** | 登録済みの上書き修正・無効化 |
| **修了証明書発行** | 修了証明書PDFを発行・ダウンロード |

データはGoogleスプレッドシートにクラウドBで保存されます。
"""
)

# 接続確認
with st.expander("接続状態を確認"):
    try:
        ss = store._spreadsheet()
        st.success(f"Googleシート接続OK：{ss.title}")
        n = len(store.read_people())
        st.write(f"登録済み修了者：{n} 件")
    except Exception as e:  # noqa: BLE001
        st.error("Googleシートに接続できません。Secretsの [gcp_service_account] と"
                 " シート共有設定を確認してください。")
        st.exception(e)
