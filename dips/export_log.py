"""出力履歴ログ（data/export_log.csv）。

列: 日時 / 管理No / 氏名 / 申請ID / 修了証明書番号 / 状態フラグ / ファイル名
氏名を含むため data_dir（Dropbox・gitignore対象）配下に保存する。
重複チェック（申請ID・修了証明書番号）と状態フラグ整合（2/3 は過去の 1 が必要）に用いる。
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

LOG_HEADER = ["日時", "管理No", "氏名", "申請ID", "修了証明書番号", "状態フラグ", "ファイル名"]


def read_log(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_log(path: str | Path, entries: list[dict]) -> None:
    p = Path(path)
    os.makedirs(p.parent, exist_ok=True)
    new_file = not p.exists()
    with open(p, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_HEADER, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        for e in entries:
            writer.writerow(e)


def applied_new_ids(log_rows: list[dict]) -> set[str]:
    """過去に「1：新規」で登録された申請IDの集合。"""
    return {r["申請ID"] for r in log_rows if str(r.get("状態フラグ", "")).strip() == "1"}


def existing_ids(log_rows: list[dict]) -> set[str]:
    return {r["申請ID"] for r in log_rows if r.get("申請ID")}


def existing_shumeisho(log_rows: list[dict]) -> set[str]:
    return {r["修了証明書番号"] for r in log_rows if r.get("修了証明書番号")}
