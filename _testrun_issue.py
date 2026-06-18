"""テスト発行スクリプト（使い捨て）。

実データ・Dropbox には触れず、リポジトリ内 _testrun/ にのみ出力する。
1件のテストレコードでパイプライン（変換→検証→CSV出力→セルフテスト）を実行し、
生成CSVの中身とバイト仕様・検証結果を表示する。

  申請ID = 1 / 各日付 = 2026/06/16 / 固有番号 0001（機関コードは仮 9999）
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from dips import config, export_log, pipeline
from dips.csv_writer import BOM
from dips.excel_reader import flatten_header as F

TODAY = dt.date(2026, 6, 17)
KIKAN = "0188"  # 実機関コード（ユーザー確認済 2026-06-16）

import os
settings, mapping, code_map, paths = config.load_all()

# USE_REAL=1 なら settings.yaml の data_dir（=Gドライブ）へ出力。
# 既定はリポジトリ内 _testrun/ に出力（実データに触れない）。
if os.environ.get("USE_REAL") != "1":
    base = Path(__file__).resolve().parent / "_testrun"
    paths.output_dir = base / "output"
    paths.log_dir = base / "data"
    paths.export_log = base / "data" / "export_log.csv"
print("出力先 data_dir/output:", paths.output_dir)

settings_values = {
    "kikan_code": KIKAN,
    "kikan_name": "テスト機関",
    "office_code_default": "99990001",
}

# master の1レコード相当（キーは flatten したヘッダー名）
record = {
    "_row": 4,
    F("管理No"): "1",
    F("氏名"): "テスト太郎",
    F("申請ID(自動=証明書番号)"): "1",
    F("技能証明申請者番号(10文字以内)"): "TEST000001",
    F("事務所コード"): "R0188001",
    F("資格区分"): "一等",
    F("停止処分者向け講習受講"): "",          # 空欄→「無」→ "1"
    F("修了証明書番号(自動)"): f"UC{KIKAN}26060002",  # UC+9999+2606+0001
    F("講習修了日"): TODAY,
    F("有効期間満了日(自動)"): dt.date(2026, 9, 16),
    F("登録種別(状態フラグ)"): "1：新規",
    F("修了証明書発行日"): TODAY,
}

history = export_log.read_log(paths.export_log)
prepared = pipeline.prepare_rows(
    [record], settings_values, code_map, mapping, settings,
    history_rows=history, today=TODAY, allow_invalidate=False)

date_str = TODAY.strftime("%Y%m%d")
now_str = "2026-06-16 00:00:00"  # 固定（Date.now系は使わない）
report = pipeline.generate(prepared, settings, paths, mapping,
                           date_str=date_str, now_str=now_str, write_log=True)

print("=" * 60)
print(f"生成ファイル数: {len(report.files)} / 書込件数: {report.total_written}")
for pr in prepared:
    print(f"\n[行変換結果] 申請ID={pr.apply_id!r} 修了証明書番号={pr.shumeisho!r}")
    print("  17列:", pr.result.values)
    if pr.field_errors:
        for e in pr.field_errors:
            print(f"  ❌ 項目エラー [列{e.index} {e.name}] {e.msg}（値:{e.value!r}）")
    if pr.integrity_errors:
        for m in pr.integrity_errors:
            print(f"  ❌ 整合エラー: {m}")
    if pr.warnings:
        for w in pr.warnings:
            print(f"  ⚠️ 警告: {w}")
    if pr.is_valid:
        print("  ✅ 検証OK（出力対象）")

for fr in report.files:
    print("\n" + "=" * 60)
    print(f"出力: {fr.path}（{fr.count}件）")
    print(f"セルフテスト: {'✅ 合格' if fr.selftest.passed else '❌ 不合格'}")
    for c in fr.selftest.checks:
        print(f"  [{'OK' if c.ok else 'NG'}] {c.name}{('  ' + c.detail) if c.detail else ''}")

    raw = Path(fr.path).read_bytes()
    print("\n--- バイト仕様 ---")
    print(f"  先頭3バイト: {raw[:3].hex()}  (BOM={'あり' if raw.startswith(BOM) else 'なし'})")
    print(f"  末尾2バイト: {raw[-2:].hex()}  (末尾改行={'あり' if raw.endswith(b'\\n') or raw.endswith(b'\\r') else 'なし'})")
    body = raw[len(BOM):]
    print(f"  LF={body.count(b'\\n')} CR={body.count(b'\\r')} CRLF={body.count(b'\\r\\n')}")
    print("\n--- 中身（CRLFを\\r\\nで可視化）---")
    print(repr(raw.decode('utf-8')))
