# -*- coding: utf-8 -*-
"""簡易ログイン（パスワード）。クラウド公開時に個人情報を保護するため。

st.secrets["app_password"] が設定されていればログインを要求する。
未設定（ローカル等）なら制限しない。各ページの先頭で require_login() を呼ぶ。
"""
from __future__ import annotations

import streamlit as st


def _password() -> str | None:
    try:
        return st.secrets.get("app_password")
    except Exception:  # noqa: BLE001 secrets未設定
        return None


def require_login() -> None:
    pw = _password()
    if not pw:                       # 未設定ならゲートしない
        return
    if st.session_state.get("_authed"):
        with st.sidebar:
            if st.button("🔓 ログアウト"):
                st.session_state["_authed"] = False
                st.rerun()
        return
    st.title("🔒 ログイン")
    st.caption("スタッフ用パスワードを入力してください。")
    entered = st.text_input("パスワード", type="password")
    if st.button("ログイン", type="primary"):
        if entered == pw:
            st.session_state["_authed"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()
