# -*- coding: utf-8 -*-
"""発注書を PDF で作成する（A4縦・税率別集計・角印対応）。

金額計算と PDF 出力だけを担い、入力元（画面フォーム）には依存しない。

data 辞書のキー:
  po_no(発注番号) / issue_date(発注日) / supplier(発注先) / honorific(敬称) /
  subject(件名) / delivery_date(納期) / delivery_place(納品場所) /
  payment_terms(支払条件) / note(備考) / items(明細) / issuer(発注者情報)

明細 items の各要素:
  name(品名・仕様) / qty(数量) / unit(単位) / price(単価) / tax_rate(税率%)
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from dips import certificate

# 明細表の列（見出し, 幅mm, 揃え）
ITEM_COLUMNS = [
    ("No", 10, "CENTER"),
    ("品名・仕様", 70, "LEFT"),
    ("数量", 16, "RIGHT"),
    ("単位", 14, "CENTER"),
    ("単価", 24, "RIGHT"),
    ("金額", 26, "RIGHT"),
    ("税率", 10, "CENTER"),
]
TITLE = "発 注 書"
DEFAULT_TAX_RATE = 10


# ============================================================
# 金額計算
# ============================================================
def _dec(v) -> Decimal:
    """数値・文字列を Decimal にする。解釈できなければ 0。"""
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v if v not in (None, "") else 0).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return Decimal(0)


def line_amount(item: dict) -> int:
    """明細1行の金額（数量×単価）。円未満は四捨五入。"""
    amount = _dec(item.get("qty")) * _dec(item.get("price"))
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def compute_totals(items: list[dict]) -> dict:
    """明細から税率別の小計・消費税・合計を求める。

    消費税は「税率ごとに1回だけ」端数処理する（切り捨て）。適格請求書の
    端数処理ルールに合わせ、明細1行ごとには消費税を計算しない。

    戻り値: {"lines": [{...,"amount":int}], "subtotal": int,
             "by_rate": {税率: {"subtotal": int, "tax": int}},
             "tax": int, "total": int}
    """
    lines, by_rate = [], {}
    for item in items:
        amount = line_amount(item)
        rate = int(_dec(item.get("tax_rate", DEFAULT_TAX_RATE)))
        lines.append({**item, "amount": amount, "tax_rate": rate})
        by_rate.setdefault(rate, {"subtotal": 0, "tax": 0})["subtotal"] += amount

    for rate, v in by_rate.items():
        tax = _dec(v["subtotal"]) * _dec(rate) / _dec(100)
        v["tax"] = int(tax.quantize(Decimal(1), rounding=ROUND_DOWN))

    subtotal = sum(v["subtotal"] for v in by_rate.values())
    tax_total = sum(v["tax"] for v in by_rate.values())
    return {"lines": lines, "subtotal": subtotal,
            "by_rate": dict(sorted(by_rate.items(), reverse=True)),
            "tax": tax_total, "total": subtotal + tax_total}


def yen(n) -> str:
    """3桁区切りの金額表記。'¥1,234' """
    return f"¥{int(n):,}"


def _qty(v) -> str:
    """数量の表示。整数なら小数点を出さない。"""
    d = _dec(v)
    return str(int(d)) if d == d.to_integral_value() else str(d.normalize())


# ============================================================
# 発注番号
# ============================================================
def next_po_no(out_dir, issue_date: dt.date, pattern: str = "PO-{date}-{seq:02d}") -> str:
    """出力先フォルダの既存PDFを見て、同じ発注日の次の連番を返す。"""
    ymd = f"{issue_date:%Y%m%d}"
    # 連番の直前までを接頭辞として取り出す（例 "PO-20260729-"）
    prefix = pattern.split("{seq")[0].format(date=ymd)
    out_dir = Path(out_dir)
    used = []
    if out_dir.exists():
        for p in out_dir.glob("*.pdf"):
            m = re.search(re.escape(prefix) + r"(\d+)", p.name)
            if m:
                used.append(int(m.group(1)))
    return pattern.format(date=ymd, seq=max(used) + 1 if used else 1)


def issuer_defaults(settings: dict) -> dict:
    """settings から発注者（自社）情報の既定値を作る。"""
    org = settings.get("organization", {}) or {}
    o = settings.get("order", {}) or {}
    return {
        "name": o.get("issuer_name") or org.get("kikan_name", ""),
        "address": o.get("issuer_address") or org.get("address", ""),
        "tel": o.get("tel", ""),
        "fax": o.get("fax", ""),
        "person": o.get("person", ""),
    }


# ============================================================
# PDF
# ============================================================
def _jdate(value) -> str:
    """date または 'YYYY/MM/DD' を 'YYYY年M月D日' にする。空なら空文字。"""
    if isinstance(value, dt.date):
        return f"{value.year}年{value.month}月{value.day}日"
    s = str(value or "").strip().replace("-", "/")
    parts = s.split("/")
    if len(parts) == 3 and all(parts):
        try:
            return f"{int(parts[0])}年{int(parts[1])}月{int(parts[2])}日"
        except ValueError:
            return s
    return s


def _styles():
    certificate._register_fonts()
    m, g = certificate.MINCHO, certificate.GOTHIC
    return {
        "title": ParagraphStyle("t", fontName=m, fontSize=22, leading=28, alignment=1),
        "body": ParagraphStyle("b", fontName=m, fontSize=10, leading=15),
        "small": ParagraphStyle("s", fontName=m, fontSize=8.5, leading=12),
        "cell": ParagraphStyle("c", fontName=m, fontSize=9, leading=12),
        "total": ParagraphStyle("g", fontName=g, fontSize=14, leading=18),
    }


def _header_block(d: dict, st: dict, issuer: dict, seal_image):
    """発注先（左）と発注番号・発注日・発注者（右）を2カラムで組む。"""
    left = [Paragraph(f"{d.get('supplier', '')}　{d.get('honorific', '御中')}", st["body"]),
            Spacer(1, 3 * mm),
            Paragraph("下記のとおり発注いたします。", st["small"])]

    right = [Paragraph(f"発注番号：{d.get('po_no', '')}", st["small"]),
             Paragraph(f"発注日：{_jdate(d.get('issue_date'))}", st["small"]),
             Spacer(1, 2 * mm),
             Paragraph(issuer.get("name", ""), st["body"])]
    for line in (issuer.get("address", ""),
                 "　".join(x for x in [f"TEL：{issuer['tel']}" if issuer.get("tel") else "",
                                       f"FAX：{issuer['fax']}" if issuer.get("fax") else ""] if x),
                 f"担当：{issuer['person']}" if issuer.get("person") else ""):
        if line:
            right.append(Paragraph(line, st["small"]))

    tbl = Table([[left, right]], colWidths=[88 * mm, 82 * mm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    if seal_image and Path(seal_image).exists():
        return _SealOverlay(tbl, seal_image)
    return tbl


class _SealOverlay(Table):
    """発注者ブロックの右下に印影を重ねて描くための薄いラッパー。"""

    SIZE = 18 * mm

    def __init__(self, inner, seal_image, total_width=170 * mm):
        super().__init__([[inner]], colWidths=[total_width])
        self.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        self._seal = seal_image
        self._total_width = total_width

    def draw(self):
        super().draw()
        x = self._total_width - self.SIZE - 2 * mm
        self.canv.drawImage(str(self._seal), x, 0, width=self.SIZE, height=self.SIZE,
                            preserveAspectRatio=True, mask="auto")


def _terms_table(d: dict, st: dict):
    """納期・納品場所・支払条件の条件表。"""
    rows = [("納期", d.get("delivery_date_text") or _jdate(d.get("delivery_date"))),
            ("納品場所", d.get("delivery_place", "")),
            ("支払条件", d.get("payment_terms", ""))]
    data = [[label, Paragraph(str(value or ""), st["cell"])] for label, value in rows]
    tbl = Table(data, colWidths=[28 * mm, 142 * mm])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.92, 0.92, 0.92)),
        ("FONTNAME", (0, 0), (-1, -1), certificate.MINCHO),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def _total_box(totals: dict, st: dict):
    """「御発注金額（税込）」の強調枠。"""
    data = [["御発注金額（税込）", yen(totals["total"])]]
    tbl = Table(data, colWidths=[50 * mm, 50 * mm])
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.92, 0.92, 0.92)),
        ("FONTNAME", (0, 0), (0, -1), certificate.MINCHO),
        ("FONTNAME", (1, 0), (1, -1), certificate.GOTHIC),
        ("FONTSIZE", (0, 0), (0, -1), 10),
        ("FONTSIZE", (1, 0), (1, -1), 13),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (1, 0), (1, -1), 5),
    ]))
    return tbl


def _items_table(totals: dict, st: dict):
    """明細表＋小計/消費税(税率別)/合計。"""
    data = [[label for label, _, _ in ITEM_COLUMNS]]
    for i, ln in enumerate(totals["lines"], start=1):
        data.append([str(i), Paragraph(str(ln.get("name", "")), st["cell"]),
                     _qty(ln.get("qty")), str(ln.get("unit", "")),
                     yen(_dec(ln.get("price")).quantize(Decimal(1), rounding=ROUND_HALF_UP)),
                     yen(ln["amount"]), f"{ln['tax_rate']}%"])

    n_items = len(totals["lines"])
    foot = [("小計（税抜）", totals["subtotal"])]
    for rate, v in totals["by_rate"].items():
        foot.append((f"消費税（{rate}%）", v["tax"]))
    foot.append(("合計（税込）", totals["total"]))
    for label, value in foot:
        data.append(["", "", "", "", label, yen(value), ""])

    widths = [w * mm for _, w, _ in ITEM_COLUMNS]
    tbl = Table(data, colWidths=widths, repeatRows=1)

    style = [
        ("GRID", (0, 0), (-1, n_items), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.90, 0.90, 0.90)),
        ("FONTNAME", (0, 0), (-1, -1), certificate.MINCHO),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        # 集計行は「単価」「金額」列のみ罫線を引く
        ("GRID", (4, n_items + 1), (5, -1), 0.5, colors.black),
        ("ALIGN", (4, n_items + 1), (4, -1), "CENTER"),
        ("ALIGN", (5, n_items + 1), (5, -1), "RIGHT"),
        ("BACKGROUND", (4, -1), (5, -1), colors.Color(0.92, 0.92, 0.92)),
        ("FONTNAME", (5, -1), (5, -1), certificate.GOTHIC),
        ("FONTSIZE", (4, -1), (5, -1), 10),
    ]
    for i, (_, _, align) in enumerate(ITEM_COLUMNS):
        style.append(("ALIGN", (i, 1), (i, n_items), align))
    tbl.setStyle(TableStyle(style))
    return tbl


def _footer(label: str):
    def draw(canv, doc):
        certificate._register_fonts()
        canv.saveState()
        canv.setFont(certificate.MINCHO, 8)
        canv.setFillGray(0.35)
        canv.drawString(20 * mm, 10 * mm, label)
        canv.drawRightString(doc.pagesize[0] - 20 * mm, 10 * mm,
                             f"- {canv.getPageNumber()} -")
        canv.restoreState()
    return draw


def generate_order(data: dict, out_path, seal_image=None) -> Path:
    """発注書PDF（A4縦）を out_path に生成して返す。"""
    st = _styles()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    issuer = data.get("issuer") or {}
    totals = compute_totals(data.get("items") or [])

    doc = BaseDocTemplate(str(out_path), pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=18 * mm,
                          title=f"発注書 {data.get('po_no', '')}",
                          author=issuer.get("name", ""))
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame],
                                       onPage=_footer(issuer.get("name", "")))])

    story = [Paragraph(TITLE, st["title"]), Spacer(1, 8 * mm),
             _header_block(data, st, issuer, seal_image), Spacer(1, 7 * mm)]
    if data.get("subject"):
        story += [Paragraph(f"件名：{data['subject']}", st["body"]), Spacer(1, 3 * mm)]
    story += [_total_box(totals, st), Spacer(1, 5 * mm),
              _terms_table(data, st), Spacer(1, 5 * mm),
              _items_table(totals, st)]
    if data.get("note"):
        story += [Spacer(1, 5 * mm),
                  KeepTogether([Paragraph("備考", st["body"]),
                                Paragraph(str(data["note"]).replace("\n", "<br/>"),
                                          st["small"])])]
    doc.build(story)
    return out_path
