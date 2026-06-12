"""code_map.yaml に基づく値変換。

対応する match モード:
  contains       … priority 順に部分一致（区分: 一等/二等。両方保有は「一等」優先で1）
  exact          … 完全一致（空欄は blank 値）
  leading_digit  … 先頭1文字を採用（状態フラグ: 「1：新規」→1）
  leading_token  … 全角/半角コロンより前を採用（講習区分: 「UC：更新講習」→UC）
"""
from __future__ import annotations

from typing import Any


class CodeMapError(ValueError):
    """値変換に失敗（未知の値など）。"""


def _norm(v: Any) -> str:
    return "" if v is None else str(v).strip()


def apply_map(raw_value: Any, table_def: dict) -> str:
    """単一の変換テーブル定義 table_def を raw_value に適用して出力値を返す。"""
    value = _norm(raw_value)
    match = table_def.get("match", "exact")
    table = table_def.get("table", {})

    if match == "exact":
        if value == "":
            if "blank" in table_def:
                return str(table_def["blank"])
            raise CodeMapError("空欄に対する変換先がありません")
        if value in table:
            return str(table[value])
        raise CodeMapError(f"未知の値: {value!r}")

    if match == "contains":
        for key in table_def.get("priority", list(table.keys())):
            if key in value:
                return str(table[key])
        raise CodeMapError(f"未知の値（部分一致なし）: {value!r}")

    if match == "leading_digit":
        if value and value[0].isdigit():
            return value[0]
        # フォールバック: テーブル完全一致
        if value in table:
            return str(table[value])
        raise CodeMapError(f"先頭が数字でない: {value!r}")

    if match == "leading_token":
        for sep in ("：", ":"):
            if sep in value:
                return value.split(sep, 1)[0].strip()
        if value in table:
            return str(table[value])
        return value

    raise CodeMapError(f"未知の match モード: {match!r}")
