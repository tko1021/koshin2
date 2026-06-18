"""手入力で発行ページの処理を通しで検証するE2Eテスト（使い捨て）。
台帳=テスト用WS `_E2Eテスト` / CSV=一時フォルダ `_testrun/e2e/` に隔離。終了後にWSは削除。
"""
from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

from dips import config, export_log, intake, pipeline, sheets

TEST_WS = "_E2Eテスト"

settings, mapping, code_map, _ = config.load_all()
org = settings.get("organization", {})
sheet_id = config.get_sheet_id(settings)
today = dt.date.today()

# --- CSV出力を一時フォルダへ隔離 ---
tmp_settings = copy.deepcopy(settings)
tmp_settings["data_dir"] = str(config.REPO_ROOT / "_testrun" / "e2e")
paths = config.Paths(tmp_settings)
paths.ensure_dirs()

# --- テスト用フォーム入力（1件） ---
form = {
    "name": "テスト 太郎", "birth_date": dt.date(1990, 4, 1), "kubun": "一等",
    "applicant_no": "TEST000001", "complete_date": today, "issue_date": today,
    "serial": 9001, "prefix": "UC", "koushi": "山田講師", "genteikaijo": "",
    "koufu": "有", "reissue_date": None, "teishi": "無", "jotai": "1：新規",
    "office_code": org.get("office_code_default", ""), "biko": "E2Eテスト",
}

dips_rec = intake.compute_row(
    form, org, holidays=[], months=settings["validity"]["months"],
    minus_days=settings["validity"]["minus_days"],
    link_due_days=settings["business_days"]["link_due_days"])
ledger = intake.build_ledger_row(
    form, org, months=settings["validity"]["months"],
    minus_days=settings["validity"]["minus_days"])

print("=== 生成された台帳行 ===")
for k, v in ledger.items():
    print(f"  {k}: {v}")

# --- 1) 台帳テストWSへ追記 ---
n = sheets.append_ledger_rows([ledger], sheet_id=sheet_id, worksheet=TEST_WS)
print(f"\n[1] 台帳WS({TEST_WS})へ {n} 件追記 OK")

# 読み戻して確認
ss = sheets.open_spreadsheet(sheet_id)
ws = ss.worksheet(TEST_WS)
print("    読み戻し最終行:", ws.get_all_values()[-1])

# --- 2) DIPS CSV発行（一時フォルダ） ---
history = export_log.read_log(paths.export_log)
prepared = pipeline.prepare_rows(
    [dips_rec], org, code_map, mapping, tmp_settings,
    history_rows=history, today=today)
report = pipeline.generate(
    prepared, tmp_settings, paths, mapping,
    date_str=today.strftime("%Y%m%d"),
    now_str=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    write_log=True)

print(f"\n[2] CSV生成: {report.total_written} 件 / {len(report.files)} ファイル")
for fr in report.files:
    print(f"    file: {fr.path} ({fr.count}件)")
    print(f"    セルフテスト: {'✅ 全合格' if fr.selftest.passed else '❌ 不合格'}")
    for c in fr.selftest.checks:
        print(f"      - {c.name}: {'OK' if c.ok else 'NG'}  {c.detail}")
if report.excluded:
    print("    ⚠️ 除外:", [(p.apply_id, list(p.integrity_errors)) for p in report.excluded])

# --- 後始末: テストWS削除 ---
ss.del_worksheet(ws)
print(f"\n[後始末] テストWS {TEST_WS} を削除しました（本番 WS・データは未接触）")
print("\n=== E2E 完了 ===")
