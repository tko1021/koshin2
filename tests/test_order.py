# -*- coding: utf-8 -*-
"""発注書（金額計算・発注番号採番・PDF生成）のテスト。"""
import datetime as dt

from dips import order

ISSUER = {"name": "テスト株式会社", "address": "岐阜県大垣市1-1",
          "tel": "0584-00-0000", "fax": "0584-00-0001", "person": "山田太郎"}

ITEMS = [
    {"name": "ドローン本体", "qty": 2, "unit": "台", "price": 350000, "tax_rate": 10},
    {"name": "予備バッテリー", "qty": 5, "unit": "個", "price": 18000, "tax_rate": 10},
    {"name": "受講者用飲料", "qty": 30, "unit": "本", "price": 130, "tax_rate": 8},
]


def _data(**over):
    d = {"po_no": "PO-20260729-01", "issue_date": dt.date(2026, 7, 29),
         "supplier": "株式会社サプライ", "honorific": "御中",
         "subject": "ドローン講習用 機材一式",
         "delivery_date": dt.date(2026, 8, 31), "delivery_place": "本社倉庫",
         "payment_terms": "月末締め翌月末払い", "note": "分納可。\n納品書を同梱のこと。",
         "items": ITEMS, "issuer": ISSUER}
    d.update(over)
    return d


# ---------- 金額計算 ----------
def test_line_amount_rounds_half_up():
    assert order.line_amount({"qty": 2, "price": 350000}) == 700000
    assert order.line_amount({"qty": 1.5, "price": 1001}) == 1502      # 1501.5 → 1502
    assert order.line_amount({"qty": 0.5, "price": 1001}) == 501       # 500.5 → 501
    assert order.line_amount({"qty": "", "price": ""}) == 0


def test_line_amount_accepts_comma_separated_text():
    assert order.line_amount({"qty": "2", "price": "1,000"}) == 2000


def test_compute_totals_by_tax_rate():
    t = order.compute_totals(ITEMS)
    assert [ln["amount"] for ln in t["lines"]] == [700000, 90000, 3900]
    # 税率ごとに集約されること
    assert t["by_rate"][10]["subtotal"] == 790000
    assert t["by_rate"][8]["subtotal"] == 3900
    # 消費税は税率ごとに1回だけ切り捨て（3900*0.08=312.0）
    assert t["by_rate"][10]["tax"] == 79000
    assert t["by_rate"][8]["tax"] == 312
    assert t["subtotal"] == 793900
    assert t["tax"] == 79312
    assert t["total"] == 873212


def test_tax_is_truncated_not_rounded():
    # 1050 * 8% = 84.0 / 1055 * 8% = 84.4 → 切り捨てで 84
    t = order.compute_totals([{"name": "x", "qty": 1, "price": 1055, "tax_rate": 8}])
    assert t["tax"] == 84
    assert t["total"] == 1139


def test_compute_totals_orders_rates_descending():
    t = order.compute_totals(ITEMS)
    assert list(t["by_rate"]) == [10, 8]


def test_compute_totals_default_rate_and_zero_rate():
    t = order.compute_totals([{"name": "既定", "qty": 1, "price": 1000},
                              {"name": "非課税", "qty": 1, "price": 500, "tax_rate": 0}])
    assert t["by_rate"][order.DEFAULT_TAX_RATE]["tax"] == 100
    assert t["by_rate"][0]["tax"] == 0
    assert t["total"] == 1600


def test_compute_totals_empty():
    t = order.compute_totals([])
    assert (t["subtotal"], t["tax"], t["total"]) == (0, 0, 0)


def test_yen():
    assert order.yen(1234567) == "¥1,234,567"
    assert order.yen(0) == "¥0"


# ---------- 発注番号 ----------
def test_next_po_no_starts_at_one(tmp_path):
    assert order.next_po_no(tmp_path, dt.date(2026, 7, 29)) == "PO-20260729-01"


def test_next_po_no_increments_and_handles_two_digits(tmp_path):
    (tmp_path / "PO-20260729-01_A社.pdf").write_bytes(b"x")
    (tmp_path / "PO-20260729-09_B社.pdf").write_bytes(b"x")
    assert order.next_po_no(tmp_path, dt.date(2026, 7, 29)) == "PO-20260729-10"
    (tmp_path / "PO-20260729-10_C社.pdf").write_bytes(b"x")
    assert order.next_po_no(tmp_path, dt.date(2026, 7, 29)) == "PO-20260729-11"


def test_next_po_no_is_per_date(tmp_path):
    (tmp_path / "PO-20260729-03_A社.pdf").write_bytes(b"x")
    assert order.next_po_no(tmp_path, dt.date(2026, 7, 30)) == "PO-20260730-01"


def test_next_po_no_missing_dir(tmp_path):
    assert order.next_po_no(tmp_path / "未作成", dt.date(2026, 7, 29)) == "PO-20260729-01"


# ---------- 発注者既定値 ----------
def test_issuer_defaults_falls_back_to_organization():
    s = {"organization": {"kikan_name": "機関名", "address": "住所"},
         "order": {"tel": "000"}}
    d = order.issuer_defaults(s)
    assert d["name"] == "機関名" and d["address"] == "住所" and d["tel"] == "000"


def test_issuer_defaults_order_section_wins():
    s = {"organization": {"kikan_name": "機関名", "address": "住所"},
         "order": {"issuer_name": "別会社", "issuer_address": "別住所"}}
    d = order.issuer_defaults(s)
    assert d["name"] == "別会社" and d["address"] == "別住所"


def test_issuer_defaults_without_order_section():
    d = order.issuer_defaults({"organization": {"kikan_name": "機関名"}})
    assert d["name"] == "機関名" and d["tel"] == ""


# ---------- PDF ----------
def test_generate_order_pdf(tmp_path):
    out = order.generate_order(_data(), tmp_path / "発注書.pdf")
    assert out.exists() and out.stat().st_size > 1000
    assert out.read_bytes().startswith(b"%PDF")


def test_generate_order_creates_parent_dir(tmp_path):
    out = order.generate_order(_data(), tmp_path / "深い" / "階層" / "発注書.pdf")
    assert out.exists()


def test_generate_order_with_text_delivery_and_no_note(tmp_path):
    out = order.generate_order(
        _data(delivery_date=None, delivery_date_text="別途協議", note="", subject=""),
        tmp_path / "発注書2.pdf")
    assert out.read_bytes().startswith(b"%PDF")


def test_generate_order_with_seal(tmp_path):
    # 印影の代わりにダミー画像を作り、押印経路を通す
    from PIL import Image
    png = tmp_path / "seal.png"
    Image.new("RGBA", (64, 64), (200, 30, 30, 255)).save(png)
    out = order.generate_order(_data(), tmp_path / "発注書3.pdf", seal_image=png)
    assert out.read_bytes().startswith(b"%PDF")


def test_generate_order_many_items_multipage(tmp_path):
    items = [{"name": f"品目{i}", "qty": 1, "unit": "個", "price": 1000, "tax_rate": 10}
             for i in range(60)]
    out = order.generate_order(_data(items=items), tmp_path / "発注書4.pdf")
    assert out.exists() and out.stat().st_size > 1000
