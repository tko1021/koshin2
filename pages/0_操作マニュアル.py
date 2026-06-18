# -*- coding: utf-8 -*-
"""操作マニュアルをアプリ内で表示するページ。

共有フォルダ（data_dir）の「操作マニュアル.md」を読み込んで表示する。
ファイルが無い場合はリポジトリ同梱のコピー、それも無ければ案内を表示。
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from dips import config

st.set_page_config(page_title="操作マニュアル", layout="wide")

settings, mapping, code_map, paths = config.load_all()

# 探索順: 共有フォルダ → リポジトリ直下
CANDIDATES = [
    Path(paths.data_dir) / "操作マニュアル.md",
    config.REPO_ROOT / "操作マニュアル.md",
]

st.title("📖 操作マニュアル")

manual_path = next((p for p in CANDIDATES if p.exists()), None)

if manual_path is None:
    st.error("操作マニュアル.md が見つかりませんでした。\n\n"
             f"次の場所に置いてください:\n- {CANDIDATES[0]}")
    st.stop()

text = manual_path.read_text(encoding="utf-8")

st.caption(f"ファイル: {manual_path}")
st.download_button("⬇️ マニュアル(.md)をダウンロード", text,
                   file_name="操作マニュアル.md", mime="text/markdown")
st.divider()
st.markdown(text)
