"""DIPS出力CSVの生成。

雛形(dips_format.csv)と完全に同一のバイト仕様で書き出す:
  - 先頭に UTF-8 BOM
  - 行区切りは CRLF
  - 最終行末に改行を付けない（trailing_newline=False）
  - クォートなし・カンマ区切り
ヘッダー行は雛形ファイルの1行目を「文字列としてそのまま」採用し、
出力時に再エンコードしてバイト一致を保証する。
"""
from __future__ import annotations

from pathlib import Path

BOM = b"\xef\xbb\xbf"
CRLF = "\r\n"


def read_template_header(template_path: str | Path) -> str:
    """雛形の1行目（BOM除去・行末CRLF除去後）を文字列で返す。"""
    raw = Path(template_path).read_bytes()
    if raw.startswith(BOM):
        raw = raw[len(BOM):]
    text = raw.decode("utf-8")
    return text.split(CRLF, 1)[0].split("\n", 1)[0]


def template_header_names(template_path: str | Path, delimiter: str = ",") -> list[str]:
    return read_template_header(template_path).split(delimiter)


def build_csv_bytes(header_line: str, rows: list[list[str]],
                    trailing_newline: bool = False, delimiter: str = ",") -> bytes:
    """ヘッダー＋データ行から出力CSVのバイト列を組み立てる。"""
    lines = [header_line]
    lines.extend(delimiter.join(r) for r in rows)
    body = CRLF.join(lines)
    if trailing_newline:
        body += CRLF
    return BOM + body.encode("utf-8")


def write_csv(path: str | Path, header_line: str, rows: list[list[str]],
              trailing_newline: bool = False, delimiter: str = ",") -> bytes:
    data = build_csv_bytes(header_line, rows, trailing_newline, delimiter)
    Path(path).write_bytes(data)
    return data
