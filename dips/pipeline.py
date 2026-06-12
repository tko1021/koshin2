"""生成パイプライン: 読込→変換→検証→分割→書出→セルフテスト→履歴。

app.py からも、CLI/テストからも使えるよう副作用（書込）を generate() に集約する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import csv_writer, export_log, selftest, validators
from .mapper import RowResult, build_row

# 出力列インデックス（1始まり）
COL_APPLY_ID = 1
COL_APPLICANT_NO = 2
COL_SHUMEISHO = 13
COL_EXPIRY = 15
COL_STATUS = 16


def _v(result: RowResult, index: int) -> str:
    return result.values[index - 1]


@dataclass
class PreparedRow:
    record: dict
    result: RowResult
    integrity_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked: bool = False             # 確認待ち等で出力対象外
    block_reason: str = ""

    @property
    def apply_id(self) -> str:
        return _v(self.result, COL_APPLY_ID)

    @property
    def applicant_no(self) -> str:
        return _v(self.result, COL_APPLICANT_NO)

    @property
    def shumeisho(self) -> str:
        return _v(self.result, COL_SHUMEISHO)

    @property
    def status_flag(self) -> str:
        return _v(self.result, COL_STATUS)

    @property
    def field_errors(self):
        return self.result.errors

    @property
    def is_valid(self) -> bool:
        return (not self.result.errors) and (not self.integrity_errors) and (not self.blocked)


def prepare_rows(records, settings_values, code_map, mapping, settings,
                 history_rows, today=None, allow_invalidate=False) -> list[PreparedRow]:
    kikan_code = settings_values.get("kikan_code", "")
    months = settings.get("validity", {}).get("months", 3)
    minus = settings.get("validity", {}).get("minus_days", 1)
    applied_ids = export_log.applied_new_ids(history_rows)
    hist_ids = export_log.existing_ids(history_rows)
    hist_shumeisho = export_log.existing_shumeisho(history_rows)

    prepared: list[PreparedRow] = []
    for rec in records:
        res = build_row(rec, settings_values, code_map, mapping, today=today)
        pr = PreparedRow(record=rec, result=res)

        # 行整合（修了証明書番号内の機関コード・発行年月、満了日）
        pr.integrity_errors += validators.check_shumeisho_consistency(
            pr.shumeisho, kikan_code, res.issue_date)
        pr.integrity_errors += validators.check_expiry(
            _v(res, COL_EXPIRY), res.issue_date, months, minus)

        # 履歴との重複
        if pr.apply_id and pr.apply_id in hist_ids:
            pr.integrity_errors.append(f"申請IDが出力履歴と重複: {pr.apply_id}")
        if pr.shumeisho and pr.shumeisho in hist_shumeisho:
            pr.integrity_errors.append(f"修了証明書番号が出力履歴と重複: {pr.shumeisho}")

        # 状態フラグ整合
        if pr.status_flag in ("2", "3") and pr.apply_id not in applied_ids:
            pr.warnings.append(
                f"状態フラグ{pr.status_flag}だが、申請ID {pr.apply_id} の「1：新規」登録実績が履歴にありません")
        if pr.status_flag == "3" and not allow_invalidate:
            pr.blocked = True
            pr.block_reason = "無効化(3)は確認が必要です"

        prepared.append(pr)

    # バッチ内の申請ID・修了証明書番号 重複
    _flag_batch_duplicates(prepared, "apply_id", "申請ID")
    _flag_batch_duplicates(prepared, "shumeisho", "修了証明書番号")
    return prepared


def _flag_batch_duplicates(prepared: list[PreparedRow], attr: str, label: str) -> None:
    seen: dict[str, int] = {}
    for pr in prepared:
        key = getattr(pr, attr)
        if key:
            seen[key] = seen.get(key, 0) + 1
    for pr in prepared:
        key = getattr(pr, attr)
        if key and seen[key] > 1:
            pr.integrity_errors.append(f"{label}がバッチ内で重複: {key}")


def split_files(valid_rows: list[PreparedRow], max_rows: int) -> list[list[PreparedRow]]:
    """同一の技能証明申請者番号が1ファイル内に1件までになるよう、かつ
    1ファイル最大 max_rows 件で分割する。"""
    files: list[list[PreparedRow]] = []
    seen_per_file: list[set] = []
    for pr in valid_rows:
        placed = False
        for i, bucket in enumerate(files):
            if len(bucket) < max_rows and pr.applicant_no not in seen_per_file[i]:
                bucket.append(pr)
                seen_per_file[i].add(pr.applicant_no)
                placed = True
                break
        if not placed:
            files.append([pr])
            seen_per_file.append({pr.applicant_no})
    return files


@dataclass
class FileResult:
    path: str
    count: int
    selftest: selftest.SelfTestReport
    rows: list[PreparedRow]


@dataclass
class GenerateReport:
    files: list[FileResult] = field(default_factory=list)
    excluded: list[PreparedRow] = field(default_factory=list)

    @property
    def total_written(self) -> int:
        return sum(f.count for f in self.files)


def generate(prepared: list[PreparedRow], settings, paths, mapping,
             date_str: str, now_str: str, write_log: bool = True) -> GenerateReport:
    out = settings["output"]
    header = csv_writer.read_template_header(paths.dips_template)
    max_rows = out.get("max_rows_per_file", 500)
    trailing = out.get("trailing_newline", False)
    pattern = out.get("filename_pattern", "修了者情報_{date}_{seq:02d}.csv")
    name_col = mapping["master_aux"]["name"]
    kanri_col = mapping["master_aux"]["kanri_no"]
    from .excel_reader import flatten_header

    valid = [pr for pr in prepared if pr.is_valid]
    excluded = [pr for pr in prepared if not pr.is_valid]

    paths.ensure_dirs()
    report = GenerateReport(excluded=excluded)
    buckets = split_files(valid, max_rows)

    for seq, bucket in enumerate(buckets, start=1):
        fname = pattern.format(date=date_str, seq=seq)
        fpath = Path(paths.output_dir) / fname
        rows = [pr.result.values for pr in bucket]
        csv_writer.write_csv(fpath, header, rows, trailing_newline=trailing)
        st = selftest.run_selftest(fpath, paths.dips_template, settings)
        report.files.append(FileResult(str(fpath), len(bucket), st, bucket))

        if write_log:
            entries = []
            for pr in bucket:
                entries.append({
                    "日時": now_str,
                    "管理No": _rec_str(pr.record, kanri_col, flatten_header),
                    "氏名": _rec_str(pr.record, name_col, flatten_header),
                    "申請ID": pr.apply_id,
                    "修了証明書番号": pr.shumeisho,
                    "状態フラグ": pr.status_flag,
                    "ファイル名": fname,
                })
            export_log.append_log(paths.export_log, entries)

    return report


def _rec_str(record: dict, column: str, flatten) -> str:
    v = record.get(flatten(column))
    return "" if v is None else str(v).strip()
