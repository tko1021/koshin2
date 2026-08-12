"""バリデーション（DIPSサーバ側チェックのローカル再現）。

field_validators … 1セル単位の検証関数（名前→関数）。mapping.yaml の validate: で指定。
forbidden_chars  … 全項目共通の禁則文字（日付項目は "/" のみ許可）。
integrity        … 行間・履歴との整合（mapper 出力後に行単位/バッチ単位で実行）。
"""
from __future__ import annotations

import datetime as _dt
import re

from . import dates

# 全項目で禁止する文字。日付項目のみ "/" を許可する。
FORBIDDEN = set('¥/;*?><_"|\',')
FORBIDDEN_EXCEPT_SLASH = FORBIDDEN - {"/"}

SHUMEISHO_RE = re.compile(r"^(UC|EL)\d{12}$")
KIKAN_RE = re.compile(r"^\d{4}$")
DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")


def find_forbidden_chars(value: str, allow_slash: bool = False) -> list[str]:
    """値に含まれる禁則文字の一覧を返す（空なら問題なし）。"""
    bad = FORBIDDEN_EXCEPT_SLASH if allow_slash else FORBIDDEN
    return sorted({ch for ch in value if ch in bad})


# ---- 単項目バリデータ: value(str) -> エラーメッセージ or None ----

def not_empty(v: str):
    return None if v != "" else "必須項目が空です"


def ascii_alnum(v: str):
    return None if re.fullmatch(r"[0-9A-Za-z]+", v or "") else "半角英数字のみ可（空白不可）"


def max_len_10(v: str):
    return None if len(v) <= 10 else "10文字以内にしてください"


def kikan_code_4digit(v: str):
    return None if KIKAN_RE.fullmatch(v or "") else "機関コードは4桁の半角数字"


def shumeisho_no(v: str):
    return None if SHUMEISHO_RE.fullmatch(v or "") else "修了証明書番号は (UC|EL)+12桁"


def _is_real_ymd(v: str) -> bool:
    if not DATE_RE.fullmatch(v or ""):
        return False
    y, m, d = (int(x) for x in v.split("/"))
    try:
        _dt.date(y, m, d)
        return True
    except ValueError:
        return False


def date_real(v: str):
    return None if _is_real_ymd(v) else "日付は yyyy/mm/dd の実在日"


def not_past(v: str, today: _dt.date | None = None):
    if not _is_real_ymd(v):
        return "日付は yyyy/mm/dd の実在日"
    today = today or _dt.date.today()
    y, m, d = (int(x) for x in v.split("/"))
    return None if _dt.date(y, m, d) >= today else "過去日は不可（当日比較）"


def one_of_12(v: str):
    return None if v in ("1", "2") else "値は 1 または 2"


def one_of_123(v: str):
    return None if v in ("1", "2", "3") else "値は 1/2/3"


FIELD_VALIDATORS = {
    "not_empty": not_empty,
    "ascii_alnum": ascii_alnum,
    "max_len_10": max_len_10,
    "kikan_code_4digit": kikan_code_4digit,
    "shumeisho_no": shumeisho_no,
    "date_real": date_real,
    "not_past": not_past,
    "one_of_12": one_of_12,
    "one_of_123": one_of_123,
}


# ---- 登録フォームの入力チェック ----

def validate_person_input(name: str, applicant_no: str, complete_date, issue_date,
                          phys_no: str = "", koushi: str = "") -> list[str]:
    """修了者登録フォームの入力を、DIPS へ出す前に検証する。

    シートに保存できてしまう値でも、CSV作成時や DIPS の一括登録で弾かれるものが
    あるため（半角英数以外の申請者番号・禁則文字・発行日が修了日より前など）、
    登録の時点で気づけるようにエラー文言の一覧を返す。空リストなら問題なし。
    """
    errs: list[str] = []

    nm = (name or "").strip()
    if not nm:
        errs.append("氏名を入力してください。")
    else:
        bad = find_forbidden_chars(nm)
        if bad:
            errs.append(f"氏名に使えない文字が含まれています: {' '.join(bad)}")

    no = (applicant_no or "").strip()
    if not no:
        errs.append("技能証明申請者番号を入力してください。")
    else:
        if ascii_alnum(no):
            errs.append("技能証明申請者番号は半角の英数字のみです"
                        "（全角文字・ハイフン・空白は使えません）。")
        if max_len_10(no):
            errs.append(f"技能証明申請者番号は10文字以内です（現在 {len(no)} 文字）。")

    comp = dates.to_date(complete_date)
    issue = dates.to_date(issue_date)
    if comp is None:
        errs.append("修了日を入力してください。")
    if issue is None:
        errs.append("証明書発行日を入力してください。")
    if comp is not None and issue is not None and issue < comp:
        errs.append(f"証明書発行日（{dates.date_to_ymd(issue)}）が"
                    f"修了日（{dates.date_to_ymd(comp)}）より前になっています。")

    pa = (phys_no or "").strip()
    if pa and ascii_alnum(pa):
        errs.append("身体適性検査証明書番号は半角の英数字のみです"
                    "（空欄にすると PA000000000000 で出力されます）。")

    ks = (koushi or "").strip()
    if ks:
        bad = find_forbidden_chars(ks)
        if bad:
            errs.append(f"担当講師に使えない文字が含まれています: {' '.join(bad)}")

    return errs


# ---- 整合チェック（行単位）----

def check_shumeisho_consistency(shumeisho: str, kikan_code: str, issue_date: _dt.date | None) -> list[str]:
    """修了証明書番号内の機関コード・発行年月の整合を確認する。"""
    errs: list[str] = []
    if not SHUMEISHO_RE.fullmatch(shumeisho or ""):
        return ["修了証明書番号の形式不正"]
    digits = shumeisho[2:]            # UC/EL を除く12桁
    code_in_no = digits[0:4]
    yymm_in_no = digits[4:8]
    if kikan_code and code_in_no != kikan_code:
        errs.append(f"番号内の機関コード({code_in_no})が設定値({kikan_code})と不一致")
    if issue_date is not None:
        expect = f"{issue_date.year % 100:02d}{issue_date.month:02d}"
        if yymm_in_no != expect:
            errs.append(f"番号内の発行年月({yymm_in_no})が発行日({expect})と不一致")
    return errs


def check_expiry(expiry: str, issue_date: _dt.date | None,
                 months: int = 3, minus_days: int = 1) -> list[str]:
    """有効期間満了日 = 発行日 + 3か月 - 1日 を確認する。"""
    if issue_date is None:
        return []
    if not _is_real_ymd(expiry):
        return ["有効期間満了日の形式不正"]
    want = dates.date_to_ymd(dates.expiry_date(issue_date, months, minus_days))
    return [] if expiry == want else [f"有効期間満了日が {want} と不一致（{expiry}）"]
