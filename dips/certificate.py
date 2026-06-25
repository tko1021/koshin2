# -*- coding: utf-8 -*-
"""無人航空機更新講習 修了証明書 PDF を生成する（公式 様式１ 準拠）。

ガイドライン 様式１「無人航空機更新講習修了証明書」のレイアウトを再現する。
1名＝A4縦1枚。代表者印（印影）は画像があれば差し込み、無ければ「印」枠を表示。

data 辞書のキー:
  cert_no(第○号) / complete_date(修了日) / expiry(有効期限) / name /
  applicant_no(技能証明申請者番号) / grade(一等/二等) / gentei(限定解除事項リスト) /
  koushi(担当講師) / kikan_name / kikan_code
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# 本番テンプレ画像（背景に敷く場合）。存在すれば使用。
TEMPLATE_BASENAMES = ["修了証明書テンプレート.png", "修了証明書テンプレート.jpg"]
# 印影（代表者印/機関印）画像。存在すれば機関名の横に重ねる。後日ここに置けば自動反映。
SEAL_BASENAMES = ["印影データ_背景透過.png", "印影.png", "代表者印.png", "機関印.png",
                  "印影.jpg", "代表者印.jpg"]

# 表の「区分」列（機体）のラベル（正式名）
GENTEI_ROWS = ["回転翼航空機（マルチ）", "回転翼航空機（ヘリ）", "飛行機"]
# 資格区分セルに選択入力する限定解除の項目
GENTEI_ITEMS = ["基本", "目視内飛行", "昼間飛行", "25kg未満"]
# 限定解除を記載する区分（現仕様ではマルチのみ表示）
MULTI_KEY = "回転翼航空機（マルチ）"


def display_gentei(gmap, grade=""):
    """限定解除事項の表示項目リストを返す（PDF・画面で共通利用）。

    ルール（PDFと画面で完全に揃える）:
      - 対象は回転翼（マルチ）の項目のみ（ヘリ・飛行機は表示しない）
      - 旧データの「目視外飛行」は「目視内飛行」に読み替える
      - 先頭に必ず「基本」を入れる（データに無くても）
      - 基本以外の項目は「○○（限定解除）」表記にする
    戻り値: 表示文字列のリスト 例 ["基本", "目視内飛行（限定解除）", ...]
    grade は呼び出し側の都合で受け取るが表示内容には影響しない。
    """
    items = (gmap or {}).get(MULTI_KEY) or []
    raw = ["目視内飛行" if x == "目視外飛行" else x for x in items]
    return ["基本"] + [f"{x}（限定解除）" for x in raw if x != "基本"]

_FONTS_READY = False
MINCHO = "JPMincho"
GOTHIC = "JPGothic"


_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"


def _register_fonts():
    global _FONTS_READY, MINCHO, GOTHIC
    if _FONTS_READY:
        return
    # 1) 同梱 IPAex フォント（クラウドLinux含めどこでも動く・PDF埋め込み）
    ipam, ipag = _FONT_DIR / "ipaexm.ttf", _FONT_DIR / "ipaexg.ttf"
    try:
        if ipam.exists() and ipag.exists():
            pdfmetrics.registerFont(TTFont("JPMincho", str(ipam)))
            pdfmetrics.registerFont(TTFont("JPGothic", str(ipag)))
            MINCHO, GOTHIC = "JPMincho", "JPGothic"
            _FONTS_READY = True
            return
    except Exception:  # noqa: BLE001
        pass
    # 2) Windows 同梱フォント（ローカルWindows）
    try:
        pdfmetrics.registerFont(TTFont("JPMincho", r"C:/Windows/Fonts/msmincho.ttc", subfontIndex=0))
        pdfmetrics.registerFont(TTFont("JPGothic", r"C:/Windows/Fonts/msgothic.ttc", subfontIndex=0))
        MINCHO, GOTHIC = "JPMincho", "JPGothic"
        _FONTS_READY = True
        return
    except Exception:  # noqa: BLE001
        pass
    # 3) reportlab 内蔵CIDフォント（最終手段）
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    MINCHO, GOTHIC = "HeiseiMin-W3", "HeiseiKakuGo-W5"
    _FONTS_READY = True


def _find(data_dir, names):
    for name in names:
        p = Path(data_dir) / name
        if p.exists():
            return p
    return None


def find_template(data_dir):
    return _find(data_dir, TEMPLATE_BASENAMES)


def find_seal(data_dir):
    return _find(data_dir, SEAL_BASENAMES)


def _jdate(s) -> str:
    """'YYYY/MM/DD' → 'YYYY年M月D日'。空なら空文字。"""
    s = str(s or "").strip().replace("-", "/")
    parts = s.split("/")
    if len(parts) == 3 and all(parts):
        try:
            return f"{int(parts[0])}年{int(parts[1])}月{int(parts[2])}日"
        except ValueError:
            return s
    return s


def _draw_seal(c, seal_image, x, y, size):
    """印影を描く。画像があれば配置、無ければ朱色の「印」枠を表示。"""
    if seal_image and Path(seal_image).exists():
        c.drawImage(str(seal_image), x, y, width=size, height=size,
                    preserveAspectRatio=True, mask="auto")
        return
    c.saveState()
    c.setStrokeColorRGB(0.78, 0.1, 0.1)
    c.setFillColorRGB(0.78, 0.1, 0.1)
    c.setLineWidth(1.1)
    c.circle(x + size / 2, y + size / 2, size / 2, stroke=1, fill=0)
    c.setFont(GOTHIC, size * 0.42)
    c.drawCentredString(x + size / 2, y + size / 2 - size * 0.16, "印")
    c.restoreState()


def _draw_gentei_table(c, d, x0, x1, y_top):
    """限定解除事項 ｜ 区分(マルチ/ヘリ/飛行機) ｜ 資格区分(一等/二等) の表を描く。

    資格区分セル（本人の等級の列）に、選択された限定解除項目を縦に並べて記載する。
    d['gentei_map'] = {'マルチ': ['基本',...], 'ヘリ': [...], '飛行機': [...]}
    """
    wA, wB = 16 * mm, 42 * mm
    xA, xB = x0, x0 + wA
    xC = xB + wB
    wC = (x1 - xC) / 2
    xD = xC + wC
    hH1, hH2, hR = 8 * mm, 7 * mm, 18 * mm
    y_h1 = y_top - hH1            # 「資格区分」の下
    y_h2 = y_h1 - hH2            # 一等/二等ヘッダの下（データ開始）
    y_r = [y_h2 - hR, y_h2 - 2 * hR, y_h2 - 3 * hR]
    y_bottom = y_r[2]

    c.setFillGray(0)
    c.setLineWidth(0.8)
    c.rect(x0, y_bottom, x1 - x0, y_top - y_bottom)
    # 横線
    c.line(xC, y_h1, x1, y_h1)        # 資格区分の下
    c.line(xB, y_h2, x1, y_h2)        # 区分/一等二等ヘッダの下（限定解除列は通す）
    c.line(xB, y_r[0], x1, y_r[0])
    c.line(xB, y_r[1], x1, y_r[1])
    # 縦線
    c.line(xB, y_bottom, xB, y_top)   # 限定解除事項｜区分（全高）
    c.line(xC, y_bottom, xC, y_top)   # 区分｜資格区分（全高）
    c.line(xD, y_h1, xD, y_bottom)    # 一等｜二等（資格区分の下から）

    # ヘッダ文字
    c.setFont(MINCHO, 10.5)
    c.drawCentredString((xC + x1) / 2, y_top - hH1 + 2.3 * mm, "資格区分")
    c.drawCentredString((xC + xD) / 2, y_h1 - hH2 + 2 * mm, "一等")
    c.drawCentredString((xD + x1) / 2, y_h1 - hH2 + 2 * mm, "二等")
    c.drawCentredString((xB + xC) / 2, (y_top + y_h2) / 2 - 1.5 * mm, "区分")
    # 限定解除事項（A列・縦中央3行）
    midA = (x0 + xB) / 2
    midAll = (y_top + y_bottom) / 2
    c.setFont(MINCHO, 10)
    c.drawCentredString(midA, midAll + 4.5 * mm, "限定")
    c.drawCentredString(midA, midAll - 0.5 * mm, "解除")
    c.drawCentredString(midA, midAll - 5.5 * mm, "事項")

    # 機体ラベル（区分列）＋ 資格区分セルへ選択項目を記載
    grade = str(d.get("grade", "")).strip()
    gmap = d.get("gentei_map") or {}
    row_top = [y_h2, y_r[0], y_r[1]]
    row_bot = [y_r[0], y_r[1], y_r[2]]
    for i, air in enumerate(GENTEI_ROWS):
        cy = (row_top[i] + row_bot[i]) / 2
        c.setFont(MINCHO, 8.5)
        c.drawCentredString((xB + xC) / 2, cy - 1.5 * mm, air)
        # マルチ行のみ記載。ヘリ・飛行機は枠のみ残し中身は空。
        if air != MULTI_KEY:
            continue
        # 表示ロジックは画面一覧と共通（display_gentei）
        disp = display_gentei(gmap, grade)
        col_cx = (xC + xD) / 2 if grade == "一等" else (xD + x1) / 2
        c.setFont(MINCHO, 8.5)
        top_y = cy + (len(disp) - 1) * 2 * mm
        for k, it in enumerate(disp):
            c.drawCentredString(col_cx, top_y - k * 4 * mm - 1 * mm, it)


def _draw_form(c, d, W, H, seal_image=None):
    L = 28 * mm
    R = W - 28 * mm
    c.setFillGray(0)

    # タイトル
    c.setFont(MINCHO, 19)
    c.drawCentredString(W / 2, H - 38 * mm, "無人航空機更新講習修了証明書")

    # 右上ブロック：第○号 / 修了 / 有効
    c.setFont(MINCHO, 11)
    c.drawRightString(R, H - 52 * mm, f"第　{d.get('cert_no','')}　号")
    c.drawRightString(R, H - 60 * mm, f"{_jdate(d.get('complete_date',''))}　修了")
    c.drawRightString(R, H - 67 * mm, f"{_jdate(d.get('expiry',''))}　まで有効")

    # 氏名 殿
    c.setFont(MINCHO, 13)
    c.drawString(L + 10 * mm, H - 83 * mm, f"{d.get('name','')}　殿")
    # 技能証明申請者番号
    c.setFont(MINCHO, 11)
    c.drawString(L + 10 * mm, H - 91 * mm, f"技能証明申請者番号：　{d.get('applicant_no','')}")

    # 本文
    c.setFont(MINCHO, 11.5)
    c.drawString(L + 6 * mm, H - 105 * mm,
                 "航空法第132条の51の規定に関し、登録更新講習機関が行う無人航空機")
    c.drawString(L, H - 112 * mm, "更新講習を修了したことを証明する。")

    # 表
    _draw_gentei_table(c, d, L, R, H - 125 * mm)

    # 担当講師
    ty = H - 208 * mm
    c.setFont(MINCHO, 11)
    c.drawString(L + 6 * mm, ty, "担当講師：")
    c.drawString(L + 28 * mm, ty, str(d.get("koushi", "")))
    c.setLineWidth(0.6)
    c.line(L + 28 * mm, ty - 1.5 * mm, R - 18 * mm, ty - 1.5 * mm)

    # 登録更新講習機関名 ＋ 印
    c.setFont(MINCHO, 11)
    c.drawRightString(R - 22 * mm, ty - 13 * mm, f"登録更新講習機関　{d.get('kikan_name','')}")
    # 団体名の下に住所を1行（印影 R-20mm/ty-19mm とは右端 R-22mm で左側に分離）
    c.setFont(MINCHO, 8.5)
    c.drawRightString(R - 22 * mm, ty - 18 * mm, d.get("address", ""))
    c.setFont(MINCHO, 11)
    _draw_seal(c, seal_image, R - 20 * mm, ty - 19 * mm, 16 * mm)
    # 機関コード
    c.drawRightString(R - 22 * mm, ty - 26 * mm,
                      f"登録更新講習機関コード：　{d.get('kikan_code','')}")


def generate_certificate(data: dict, out_path, template_image=None,
                         seal_image=None) -> Path:
    """1名分の修了証明書PDFを out_path に生成して返す（公式 様式１ 準拠）。"""
    _register_fonts()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=A4)
    W, H = A4
    if template_image and Path(template_image).exists():
        # 背景テンプレ画像モード（座標は本番テンプレ受領後に要調整）
        c.drawImage(str(template_image), 0, 0, width=W, height=H,
                    preserveAspectRatio=False, mask="auto")
    _draw_form(c, data, W, H, seal_image)
    c.showPage()
    c.save()
    return out_path
