# -*- coding: utf-8 -*-
"""帳票（修了者名簿・講習実施記録）を PDF / Excel で生成する。

登録更新講習機関が保存・提出する帳票を master.xlsx（ローカル版）または
Googleシート（クラウド版）の修了者データから作成する。データ取得元に依存しない
よう、入力は共通の「名簿行 dict のリスト」に正規化してから渡す。

名簿行 dict のキー:
  no / koushu(講習区分) / grade(等級区分) / name / birth / applicant_no /
  complete_date(修了日) / issue_date(証明書発行日) / cert_no(修了証明書番号) /
  expiry(有効期間満了日) / koushi(担当講師) / gentei(限定解除事項)
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)
from reportlab.lib.styles import ParagraphStyle

from dips import certificate

# ============================================================
# 帳票定義（見出し, 行dictのキー, PDF列幅mm, Excel列幅）
# ============================================================
ROSTER_COLUMNS = [
    ("No", "no", 10, 5),
    ("講習区分", "koushu", 26, 14),
    ("等級", "grade", 12, 6),
    ("氏名", "name", 34, 18),
    ("生年月日", "birth", 24, 12),
    ("技能証明申請者番号", "applicant_no", 30, 18),
    ("修了日", "complete_date", 24, 12),
    ("発行日", "issue_date", 24, 12),
    ("修了証明書番号", "cert_no", 34, 18),
    ("有効期間満了日", "expiry", 24, 14),
    ("担当講師", "koushi", 26, 14),
]

RECORD_COLUMNS = [
    ("No", "no", 10, 5),
    ("実施日（修了日）", "date", 28, 16),
    ("講習区分", "koushu", 26, 14),
    ("一等", "grade1", 12, 6),
    ("二等", "grade2", 12, 6),
    ("計", "total", 12, 6),
    ("担当講師", "koushi", 34, 18),
    ("受講者氏名", "names", 114, 48),
]

ROSTER_TITLE = "無人航空機更新講習 修了者名簿"
RECORD_TITLE = "無人航空機更新講習 実施記録"


# ============================================================
# データ整形
# ============================================================
def build_roster_rows(people: list[dict]) -> list[dict]:
    """修了者 dict のリストを名簿行へ正規化する（Noを1から振り直す）。

    people の各要素は pages/6_修了証明書発行.py の read_people() や
    cloud/_common.py の to_cert_data() と同じキーを想定し、欠けていれば空欄にする。
    """
    rows = []
    for i, p in enumerate(people, start=1):
        gentei = p.get("gentei")
        if gentei is None:
            gentei = "・".join(certificate.display_gentei(p.get("gentei_map"),
                                                         p.get("grade", "")))
        rows.append({
            "no": i,
            "koushu": str(p.get("koushu") or "更新講習"),
            "grade": str(p.get("grade") or ""),
            "name": str(p.get("name") or ""),
            "birth": str(p.get("birth") or ""),
            "applicant_no": str(p.get("applicant_no") or ""),
            "complete_date": str(p.get("complete_date") or ""),
            "issue_date": str(p.get("issue_date") or ""),
            "cert_no": str(p.get("cert_no") or ""),
            "expiry": str(p.get("expiry") or ""),
            "koushi": str(p.get("koushi") or ""),
            "gentei": gentei,
        })
    return rows


def build_record_rows(rows: list[dict]) -> list[dict]:
    """名簿行を「修了日 × 講習区分」で集計し、講習実施記録の行を作る。"""
    groups: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["complete_date"], r["koushu"])
        g = groups.setdefault(key, {"date": r["complete_date"], "koushu": r["koushu"],
                                    "grade1": 0, "grade2": 0,
                                    "_koushi": [], "_names": []})
        if r["grade"] == "一等":
            g["grade1"] += 1
        elif r["grade"] == "二等":
            g["grade2"] += 1
        if r["koushi"] and r["koushi"] not in g["_koushi"]:
            g["_koushi"].append(r["koushi"])
        g["_names"].append(r["name"])

    out = []
    for i, key in enumerate(sorted(groups), start=1):
        g = groups[key]
        out.append({
            "no": i, "date": g["date"], "koushu": g["koushu"],
            "grade1": g["grade1"], "grade2": g["grade2"],
            "total": g["grade1"] + g["grade2"],
            "koushi": "、".join(g["_koushi"]),
            "names": "、".join(g["_names"]),
        })
    return out


def renumber(rows: list[dict]) -> list[dict]:
    """名簿行の No を1から振り直した新しいリストを返す（元のリストは変更しない）。"""
    out = [dict(r) for r in rows]
    for i, r in enumerate(out, start=1):
        r["no"] = i
    return out


def filter_by_period(rows: list[dict], start: dt.date | None, end: dt.date | None,
                     key: str = "complete_date") -> list[dict]:
    """名簿行を期間で絞り込み、Noを振り直して返す。境界は両端を含む。

    start / end が両方 None の場合は日付を判定に使わず全件を残す（Noのみ振り直す）。
    日付が解釈できない行は、期間指定があるときのみ除外する。
    """
    if start is None and end is None:
        return renumber(rows)

    def _in(r):
        d = parse_date(r.get(key))
        if d is None:
            return False
        return not ((start and d < start) or (end and d > end))

    return renumber([r for r in rows if _in(r)])


def parse_date(s) -> dt.date | None:
    """'YYYY/MM/DD' / 'YYYY-MM-DD' を date にする。解釈できなければ None。"""
    parts = str(s or "").strip().replace("-", "/").split("/")
    if len(parts) != 3:
        return None
    try:
        return dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


# ============================================================
# PDF
# ============================================================
def _styles():
    certificate._register_fonts()
    mincho, gothic = certificate.MINCHO, certificate.GOTHIC
    return (
        ParagraphStyle("title", fontName=mincho, fontSize=15, leading=20,
                       alignment=1),
        ParagraphStyle("sub", fontName=mincho, fontSize=9, leading=13),
        ParagraphStyle("cell", fontName=mincho, fontSize=8, leading=10.5),
        gothic,
    )


def _footer(kikan_label: str):
    """全ページ共通のフッタ（左＝機関名 / 右＝ページ番号）を描く関数を返す。"""
    def draw(canv, doc):
        certificate._register_fonts()
        canv.saveState()
        canv.setFont(certificate.MINCHO, 8)
        canv.setFillGray(0.35)
        canv.drawString(15 * mm, 10 * mm, kikan_label)
        canv.drawRightString(doc.pagesize[0] - 15 * mm, 10 * mm, f"- {canv.getPageNumber()} -")
        canv.restoreState()
    return draw


def _table(columns, rows, cell_style, wrap_keys=(), center_keys=()):
    """列定義と行dictから Table を組む。

    wrap_keys の列は折り返し、center_keys の列は中央揃えにする。
    """
    header = [Paragraph(f"<b>{label}</b>", cell_style) for label, _, _, _ in columns]
    data = [header]
    for r in rows:
        data.append([Paragraph(str(r.get(key, "")), cell_style) if key in wrap_keys
                     else str(r.get(key, "")) for _, key, _, _ in columns])

    style = []
    for i, (_, key, _, _) in enumerate(columns):
        if key in center_keys:
            style.append(("ALIGN", (i, 1), (i, -1), "CENTER"))

    tbl = Table(data, colWidths=[w * mm for _, _, w, _ in columns], repeatRows=1)
    tbl.setStyle(TableStyle(style + [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.90, 0.90, 0.90)),
        ("FONTNAME", (0, 0), (-1, -1), certificate.MINCHO),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def _build_pdf(out_path, org, title, subtitle, columns, rows, wrap_keys=(),
               center_keys=()):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    title_s, sub_s, cell_s, _ = _styles()

    kikan = f"{org.get('kikan_name', '')}（登録更新講習機関コード：{org.get('kikan_code', '')}）"
    doc = BaseDocTemplate(str(out_path), pagesize=landscape(A4),
                          leftMargin=15 * mm, rightMargin=15 * mm,
                          topMargin=15 * mm, bottomMargin=18 * mm,
                          title=title, author=org.get("kikan_name", ""))
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame],
                                       onPage=_footer(kikan))])

    story = [Paragraph(title, title_s), Spacer(1, 5 * mm),
             Paragraph(kikan, sub_s), Paragraph(subtitle, sub_s), Spacer(1, 4 * mm)]
    if rows:
        story.append(_table(columns, rows, cell_s, wrap_keys, center_keys))
    else:
        story.append(Paragraph("該当するデータがありません。", sub_s))
    doc.build(story)
    return out_path


def roster_pdf(rows: list[dict], out_path, org: dict,
               period: str = "", title: str = ROSTER_TITLE) -> Path:
    """修了者名簿PDF（A4横）を生成する。"""
    sub = (f"作成日：{_jp(dt.date.today())}　／　対象：{period or '全件'}"
           f"　／　{len(rows)}名")
    return _build_pdf(out_path, org, title, sub, ROSTER_COLUMNS, rows,
                      center_keys=("grade", "birth", "complete_date", "issue_date",
                                   "expiry"))


def record_pdf(rows: list[dict], out_path, org: dict,
               period: str = "", title: str = RECORD_TITLE) -> Path:
    """講習実施記録PDF（A4横）を生成する。"""
    total = sum(r["total"] for r in rows)
    sub = (f"作成日：{_jp(dt.date.today())}　／　対象：{period or '全件'}"
           f"　／　{len(rows)}回・延べ{total}名")
    return _build_pdf(out_path, org, title, sub, RECORD_COLUMNS, rows,
                      wrap_keys=("names", "koushi"),
                      center_keys=("date", "grade1", "grade2", "total"))


def _jp(d: dt.date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


# ============================================================
# Excel
# ============================================================
_THIN = Side(style="thin", color="000000")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _build_xlsx(out_path, org, title, subtitle, columns, rows, sheet_name):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ncol = len(columns)

    ws.cell(row=1, column=1, value=title).font = Font(size=14, bold=True)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws.cell(row=2, column=1,
            value=f"{org.get('kikan_name', '')}（登録更新講習機関コード："
                  f"{org.get('kikan_code', '')}）")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    ws.cell(row=3, column=1, value=subtitle)
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncol)

    head = 5
    fill = PatternFill("solid", fgColor="DDDDDD")
    for j, (label, _, _, width) in enumerate(columns, start=1):
        c = ws.cell(row=head, column=j, value=label)
        c.font = Font(bold=True)
        c.fill = fill
        c.border = _BORDER
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = width

    for i, r in enumerate(rows):
        for j, (_, key, _, _) in enumerate(columns, start=1):
            c = ws.cell(row=head + 1 + i, column=j, value=r.get(key, ""))
            c.border = _BORDER
            c.alignment = Alignment(vertical="center", wrap_text=True)

    ws.freeze_panes = ws.cell(row=head + 1, column=1)
    wb.save(out_path)
    return out_path


def roster_xlsx(rows: list[dict], out_path, org: dict,
                period: str = "", title: str = ROSTER_TITLE) -> Path:
    """修了者名簿Excelを生成する（限定解除事項の列を末尾に追加）。"""
    columns = ROSTER_COLUMNS + [("限定解除事項", "gentei", 0, 30)]
    sub = f"作成日：{_jp(dt.date.today())}　／　対象：{period or '全件'}　／　{len(rows)}名"
    return _build_xlsx(out_path, org, title, sub, columns, rows, "修了者名簿")


def record_xlsx(rows: list[dict], out_path, org: dict,
                period: str = "", title: str = RECORD_TITLE) -> Path:
    """講習実施記録Excelを生成する。"""
    total = sum(r["total"] for r in rows)
    sub = (f"作成日：{_jp(dt.date.today())}　／　対象：{period or '全件'}"
           f"　／　{len(rows)}回・延べ{total}名")
    return _build_xlsx(out_path, org, title, sub, RECORD_COLUMNS, rows, "講習実施記録")
