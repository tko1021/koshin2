# -*- coding: utf-8 -*-
"""操作マニュアルを表示。"""
from pathlib import Path

import streamlit as st

import _common
from dips import auth

st.set_page_config(page_title="操作マニュアル", layout="wide")
auth.require_login()

st.title("📖 操作マニュアル")
md = Path(_common.__file__).resolve().parent.parent / "assets" / "操作マニュアル.md"
if md.exists():
    st.markdown(md.read_text(encoding="utf-8"))
else:
    st.error(f"操作マニュアルが見つかりません: {md}")
