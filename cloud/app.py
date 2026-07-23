# -*- coding: utf-8 -*-
"""DIPS更新修了者 管理アプリ（クラウド版）ホーム。

データはGoogleスプレッドシート、認証はパスワード（Streamlit Secrets）。
"""
import streamlit as st

import _common  # noqa: F401  sys.path 設定（dips を import 可能に）
from dips import auth, store

st.set_page_config(page_title="DIPS更新修了者 管理", layout="wide")
auth.require_login()

st.title("🚀 経営プラットフォーム")
st.caption(f"機関コード: {_common.KIKAN}　|　{_common.ORG.get('kikan_name','')}")

try:
    st.page_link("pages/6_代表ダッシュボード.py",
                 label="まずはここから → 代表ダッシュボード", icon="📊")
    st.page_link("pages/0_操作マニュアル.py",
                 label="はじめての方はこちら → 操作マニュアル", icon="📖")
except Exception:  # noqa: BLE001 古いStreamlit
    pass

st.markdown(
    """
既存事業（ドローンスクール）と新規構想（衣装アプリ）、日々のメモを一枚に統合し、
**選択と集中**で意思決定するためのプラットフォームです。左のサイドバーから操作してください。

#### 経営（選択と集中）
| ページ | 用途 |
|---|---|
| **代表ダッシュボード** | 現状KPI・事業ポートフォリオ・選択と集中マトリクス |
| **衣装アプリ構想** | 新規事業アイデアの構造化と検証 |
| **メモ** | 現状・気づき・アイデアを事業に紐づけて記録 |

#### 既存事業（ドローンスクール / DIPS）
| ページ | 用途 |
|---|---|
| **修了者を登録** | 修了者を新しく登録（担当講師・限定解除も） |
| **一覧・編集** | 登録内容の確認・修正・削除 |
| **DIPS_CSV作成** | DIPS登録用CSV（公式17列）を作成・ダウンロード |
| **DIPS訂正** | 登録済みの上書き修正・無効化 |
| **修了証明書発行** | 修了証明書PDFを発行・ダウンロード |

データはGoogleスプレッドシートに保存されます（メモは「経営メモ」タブ）。
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
