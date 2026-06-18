# -*- coding: utf-8 -*-
"""クラウド版の共通処理。

- リポジトリルートを sys.path に追加して共有パッケージ dips を再利用
- Googleシート(store)の修了者 → 派生値計算 / DIPSレコード / 証明書データへの変換
- CSV生成用の一時 Paths
"""
from __future__ import annotations

import base64
import copy
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dips import config, dates, intake, store  # noqa: E402

settings, mapping, code_map, _paths = config.load_all()
ORG = settings.get("organization", {})
KIKAN = ORG.get("kikan_code", "")
MONTHS = settings["validity"]["months"]
MINUS = settings["validity"]["minus_days"]
LINK_DUE = settings["business_days"]["link_due_days"]

PREFIX = {"更新講習": "UC", "失効再交付講習": "EL"}
JOTAI = {"新規": "1：新規", "上書き修正": "2：上書き修正", "無効化": "3：無効化"}
GENTEI_COLS = {
    "回転翼航空機（マルチ）": "限定解除（回転翼マルチ）",
    "回転翼航空機（ヘリ）": "限定解除（回転翼ヘリ）",
    "飛行機": "限定解除（飛行機）",
}


def _split(v):
    return [s for s in str(v).replace(",", "、").split("、") if s.strip()] if v else []


def enrich(people):
    """store.read_people() の各行に派生値（証明書番号・固有番号・有効期限等）を付与。"""
    serial_by_ym: dict[str, int] = {}
    out = []
    for p in people:
        issue = dates.to_date(p.get("証明書発行日"))
        if issue is None:
            continue
        ym = f"{issue.year % 100:02d}{issue.month:02d}"
        serial_by_ym[ym] = serial_by_ym.get(ym, 0) + 1
        prefix = PREFIX.get(p.get("講習区分", "更新講習"), "UC")
        e = dict(p)
        e["_issue"] = issue
        e["_comp"] = dates.to_date(p.get("修了日")) or issue
        e["_serial"] = serial_by_ym[ym]
        e["_prefix"] = prefix
        e["_cert"] = intake.build_shumeisho_no(prefix, KIKAN, issue, serial_by_ym[ym])
        e["_expiry"] = dates.expiry_date(issue, MONTHS, MINUS)
        out.append(e)
    return out


def to_record(e, jotai_override: str | None = None):
    """enrich済みの1名 → intake.compute_row のDIPSレコード。"""
    form = {
        "name": e.get("氏名", ""), "birth_date": None, "kubun": e.get("等級区分", "一等"),
        "applicant_no": str(e.get("技能証明申請者番号", "")), "complete_date": e["_comp"],
        "issue_date": e["_issue"], "serial": e["_serial"], "prefix": e["_prefix"],
        "koushi": "", "genteikaijo": "", "koufu": "有", "reissue_date": None,
        "teishi": e.get("停止処分者向け講習受講有無") or "無",
        "jotai": jotai_override or JOTAI.get(e.get("状態") or "新規", "1：新規"),
        "office_code": ORG.get("office_code_default", ""), "biko": "",
    }
    return intake.compute_row(form, ORG, holidays=[], months=MONTHS,
                              minus_days=MINUS, link_due_days=LINK_DUE)


def to_cert_data(e):
    """enrich済みの1名 → certificate.generate_certificate の data。"""
    return {
        "kikan_name": ORG.get("kikan_name", ""), "kikan_code": KIKAN,
        "cert_no": e["_cert"], "name": e.get("氏名", ""),
        "applicant_no": str(e.get("技能証明申請者番号", "")), "grade": e.get("等級区分", ""),
        "gentei_map": {air: _split(e.get(col)) for air, col in GENTEI_COLS.items()},
        "koushi": e.get("担当講師") or "",
        "complete_date": dates.date_to_ymd(e["_comp"]),
        "expiry": dates.date_to_ymd(e["_expiry"]),
    }


_seal_done = False
_seal_path = None


def get_seal_path():
    """印影画像のパスを返す。クラウドは Secrets(seal_png_base64)、ローカルは assets/印影.png。"""
    global _seal_done, _seal_path
    if _seal_done:
        return _seal_path
    # 1) Streamlit Secrets の seal_png_base64
    try:
        import streamlit as st
        b64 = st.secrets.get("seal_png_base64")
        if b64:
            f = Path(tempfile.gettempdir()) / "koshin_seal.png"
            f.write_bytes(base64.b64decode(b64))
            _seal_path = f
            _seal_done = True
            return _seal_path
    except Exception:  # noqa: BLE001
        pass
    # 2) Googleシート(_seal タブ)から（クラウドの主経路・Secrets不要）
    try:
        b64 = store.get_seal_b64()
        if b64:
            f = Path(tempfile.gettempdir()) / "koshin_seal.png"
            f.write_bytes(base64.b64decode(b64))
            _seal_path = f
            _seal_done = True
            return _seal_path
    except Exception:  # noqa: BLE001
        pass
    # 3) ローカル assets/印影.png
    local = _ROOT / "assets" / "印影.png"
    _seal_path = local if local.exists() else None
    _seal_done = True
    return _seal_path


def temp_paths():
    """CSV生成用の一時 Paths（/tmp）。dips_template はリポジトリ相対で有効。"""
    tmp = copy.deepcopy(settings)
    tmp["data_dir"] = tempfile.mkdtemp(prefix="koshin_csv_")
    p = config.Paths(tmp)
    p.ensure_dirs()
    return tmp, p
