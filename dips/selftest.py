"""出力後セルフテスト。

生成済みCSVを再読込し、雛形(dips_format.csv)と同一のバイト仕様かを検証する:
  BOM / ヘッダー完全一致 / 列数17 / 行区切りCRLF / 末尾改行なし
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .csv_writer import BOM, read_template_header


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SelfTestReport:
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)


def run_selftest(file_path: str | Path, template_path: str | Path,
                 settings: dict | None = None, expected_columns: int = 17) -> SelfTestReport:
    cfg = (settings or {}).get("selftest", {}) if settings else {}
    data = Path(file_path).read_bytes()
    checks: list[Check] = []

    has_bom = data.startswith(BOM)
    body = data[len(BOM):] if has_bom else data

    if cfg.get("check_bom", True):
        checks.append(Check("BOM(EF BB BF)", has_bom,
                            "" if has_bom else "先頭BOMがありません"))

    # ヘッダー完全一致
    if cfg.get("check_header_exact", True):
        try:
            file_header = body.split(b"\r\n", 1)[0].decode("utf-8")
        except UnicodeDecodeError:
            file_header = None
        tmpl_header = read_template_header(template_path)
        ok = file_header == tmpl_header
        checks.append(Check("ヘッダー完全一致", ok,
                            "" if ok else f"不一致\n 雛形 : {tmpl_header}\n 出力 : {file_header}"))

    # 列数
    if cfg.get("check_column_count", True):
        cols = expected_columns if isinstance(cfg.get("check_column_count"), bool) \
            else int(cfg.get("check_column_count") or expected_columns)
        text = body.decode("utf-8", errors="replace")
        lines = [ln for ln in text.split("\r\n") if ln != ""]
        bad = [i + 1 for i, ln in enumerate(lines) if len(ln.split(",")) != cols]
        ok = not bad
        checks.append(Check(f"列数={cols}", ok,
                            "" if ok else f"列数不一致の行: {bad}"))

    # 行区切りCRLF
    if cfg.get("check_line_sep_crlf", True):
        n_lf = body.count(b"\n")
        n_crlf = body.count(b"\r\n")
        n_cr = body.count(b"\r")
        ok = (n_lf == n_crlf == n_cr)
        checks.append(Check("行区切りCRLF", ok,
                            "" if ok else f"LF={n_lf} CR={n_cr} CRLF={n_crlf}（孤立改行あり）"))

    # 末尾改行なし
    if cfg.get("check_no_trailing_newline", True):
        ok = not data.endswith(b"\n") and not data.endswith(b"\r")
        checks.append(Check("末尾改行なし", ok,
                            "" if ok else "末尾に改行があります"))

    return SelfTestReport(checks)
