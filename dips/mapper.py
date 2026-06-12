"""master レコード → DIPS出力17列 への変換。

mapping.yaml の columns 定義に従って 1 レコードを 17 個の文字列へ変換し、
mapping.yaml の validate: と禁則文字チェックを field レベルで適用する。
行間・履歴の整合は validators.check_* / pipeline 側で行う。
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from . import codemap, dates, validators
from .excel_reader import flatten_header


@dataclass
class FieldError:
    index: int
    name: str
    value: str
    msg: str


@dataclass
class RowResult:
    values: list[str]                       # 17列の出力文字列
    errors: list[FieldError] = field(default_factory=list)
    issue_date: _dt.date | None = None      # 整合チェック用（発行日）


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, _dt.datetime):
        return value.isoformat()
    return str(value).strip()


def _get_master(record: dict, column: str) -> Any:
    return record.get(flatten_header(column))


def _resolve_source(source: dict, record: dict, settings_values: dict,
                    code_map: dict) -> tuple[str, bool]:
    """source 定義を解決して (出力文字列, is_date) を返す。"""
    stype = source["type"]
    is_date = source.get("format") == "date_ymd"

    if stype == "fixed":
        if "ref" in source:
            return str(code_map["fixed"][source["ref"]]), False
        return str(source.get("value", "")), False

    if stype == "setting":
        return _stringify(settings_values.get(source["key"], "")), False

    if stype == "master":
        raw = _get_master(record, source["column"])
        if (raw is None or _stringify(raw) == "") and "default" in source:
            return _resolve_source(source["default"], record, settings_values, code_map)
        # 日付書式
        if is_date:
            d = dates.to_date(raw)
            return (dates.date_to_ymd(d) if d is not None else _stringify(raw)), True
        # 値変換
        if "map" in source:
            try:
                return codemap.apply_map(raw, code_map[source["map"]]), False
            except codemap.CodeMapError as e:
                # 変換不能はそのまま文字列化し、後段の validate でエラー化させる
                return f"<変換不能:{_stringify(raw)}>", False
        return _stringify(raw), False

    raise ValueError(f"未知の source.type: {stype!r}")


def build_row(record: dict, settings_values: dict, code_map: dict,
              mapping: dict, today: _dt.date | None = None) -> RowResult:
    columns = sorted(mapping["columns"], key=lambda c: c["index"])
    values: list[str] = []
    errors: list[FieldError] = []

    for col in columns:
        idx, name = col["index"], col["name"]
        source = col["source"]
        value, is_date = _resolve_source(source, record, settings_values, code_map)
        values.append(value)

        # 禁則文字（日付項目のみ "/" 許可）
        bad = validators.find_forbidden_chars(value, allow_slash=is_date)
        if bad:
            errors.append(FieldError(idx, name, value, f"禁則文字: {' '.join(bad)}"))

        # 必須
        if col.get("required") and value == "":
            errors.append(FieldError(idx, name, value, "必須項目が空です"))

        # field validators
        for vname in col.get("validate", []):
            fn = validators.FIELD_VALIDATORS.get(vname)
            if fn is None:
                continue
            kwargs = {"today": today} if (vname == "not_past" and today) else {}
            msg = fn(value, **kwargs) if kwargs else fn(value)
            if msg:
                errors.append(FieldError(idx, name, value, msg))

    # 発行日（整合チェック用）
    issue_col = mapping["master_aux"]["issue_date"]
    issue_date = dates.to_date(_get_master(record, issue_col))

    return RowResult(values=values, errors=errors, issue_date=issue_date)
