"""ダウンロード済みのサービスアカウントJSON鍵を secrets/service_account.json に配置する補助。

Downloads 系フォルダから "type": "service_account" のJSONを探して配置する。
複数見つかった場合は一覧表示のみ（手動で選んで配置）。秘密鍵本文は表示しない。

  実行: <venv>\\Scripts\\python.exe scripts\\place_key.py
"""
from __future__ import annotations

import glob
import json
import os
import pathlib
import shutil

ROOTS = [
    r"C:\Users\iishi\Downloads",
    r"C:\Users\iishi\OneDrive\Documents\Downloads",
    r"C:\Users\iishi\OneDrive\Downloads",
]
DEST = pathlib.Path(__file__).resolve().parent.parent / "secrets" / "service_account.json"


def find_keys():
    found = []
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        for f in glob.glob(os.path.join(root, "*.json")):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            if d.get("type") == "service_account" and d.get("client_email"):
                found.append((f, d["client_email"], d.get("project_id")))
    return found


def main():
    cands = find_keys()
    print("サービスアカウントJSON候補数:", len(cands))
    for f, email, proj in cands:
        print("  -", f, "|", email, "|", proj)
    if len(cands) == 1:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cands[0][0], DEST)
        print("配置完了:", DEST)
        print("SAメール:", cands[0][1], "← このメールを台帳シートに『編集者』で共有")
    elif not cands:
        print("Downloadsにサービスアカウント鍵(JSON)が見つかりません。")
        print("GCPでJSON鍵をダウンロードしてから再実行してください。")
    else:
        print("複数見つかりました。使うファイルのパスを教えてください（手動配置します）。")


if __name__ == "__main__":
    main()
