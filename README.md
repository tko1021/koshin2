# koshin — DIPS 更新修了者情報CSV作成システム

登録更新講習機関の修了者マスタ（`master.xlsx`）から、DIPS「更新修了者情報一括登録」へ
アップロードする公式様式CSV（17列・UTF-8 BOM・CRLF）を生成・検証する**完全ローカル**の
ツールです。仕様は DIPS操作マニュアル＜更新講習修了者情報連携編＞Ver2026/3/23 及び
国交省ガイドラインに準拠します。外部送信は一切行いません。

---

## データとコードの分離（重要・個人情報保護）

| | 場所 | 内容 |
|---|---|---|
| **コード** | GitHub プライベートリポジトリ（`koshin`） | `app.py` / `config/` / `dips/` / `tests/` |
| **データ** | Dropbox 共有フォルダ `★ドローンスクール関係/登録更新機関/修了者管理/` | `master.xlsx`、`output/`（生成CSV）、`data/`（履歴ログ） |

- 修了者の氏名・住所等の個人情報は **Git に絶対入れません**。`.gitignore` で
  `input/ data/ output/ *.xlsx *.csv` を除外済みです。
- **マスタExcelは同時編集で「競合コピー」が発生します。編集は必ず1人ずつ**行ってください。
- データの保管先は `config/settings.yaml` の `data_dir` で変更できます。

---

## セットアップ

> **venv はリポジトリの外に作成してください。** リポジトリは Dropbox 同期下にあるため、
> `.venv` を中に置くと同期がファイルをロックし `pip` が WinError 32 で失敗します。

```powershell
# 1. Python 3.11+（検証は 3.12.10）
winget install Python.Python.3.12

# 2. リポジトリ外に venv を作成
python -m venv C:/Users/iishi/.venvs/koshin

# 3. 依存インストール
C:/Users/iishi/.venvs/koshin/Scripts/python -m pip install -r requirements.txt

# 4. 起動
C:/Users/iishi/.venvs/koshin/Scripts/streamlit run app.py
```

最初に **master.xlsx の「設定」シート**へ、機関コード(4桁)・機関名・事務所コード既定値を
入力してください（未入力だと出力が機関コード `0000` のままになります）。

---

## 運用フロー

```
講習修了
  → master.xlsx に修了者情報を入力（緑色列は自動計算。入力禁止）
  → 本アプリで対象行を選択しCSV出力（発行日から5営業日以内）
  → DIPS「更新修了者情報一括登録」へアップロード
  → 登録完了後、master.xlsx の「登録状況」を「登録済」に、「DIPS登録日」を記録
```

- **DIPS連携期限＝修了証明書発行日から5営業日**（土日＋「祝日」シートを除外）。
  アプリの一覧で 🔴超過 / 🟡間近 を色分け表示します。
- 1ファイル最大500件。**同一の技能証明申請者番号は1ファイルに1件まで**（自動分割します）。
- 出力後は生成ファイルを再読込し、雛形と **BOM・ヘッダー完全一致・列数17・CRLF・
  末尾改行なし** を自動セルフテストします。

### 受講者側の事前準備（重要）

受講者は **DIPS2.0 で当機関の事務所コードを登録済み**である必要があります。
未登録のままだと、アップロード時に DIPS 側で「未登録の番号」エラーとなり登録できません。
受講者への事前案内を行ってください。

---

## 設定ファイル（`config/`）

| ファイル | 役割 |
|---|---|
| `settings.yaml` | `data_dir`・出力仕様（BOM/CRLF/500件/ファイル名）・期限/満了日ルール・セルフテスト基準 |
| `mapping.yaml` | 出力17列 ← master列 の対応（master列は**ヘッダー名**で参照。列順ハードコードなし） |
| `code_map.yaml` | 値変換表（区分・停止処分・状態フラグ・UC/EL接頭辞）と固定値 |

### code_map.yaml の確認方法（変換ルール）

- **区分**: 資格区分 `一等→1` / `二等→2`（両方保有は `1`）
- **停止処分者向け講習受講有無**（※直感と逆）: `無/空欄→1` / `有→2`
- **状態フラグ**: 登録種別 `1：新規→1` / `2：上書き修正→2` / `3：無効化→3`
- **検査証明書番号**: 常に固定 `PA000000000000`（masterの内部PA番号は出力しません）

### 様式改定時の追従手順

DIPSの様式やmasterの列が変わった場合、原則 **コード修正なし**で追従できます。

1. 新しい公式雛形を `input/dips_format.csv` に置き換える（**出力ヘッダーの正は常にこのファイル**）。
2. 列の対応が変わったら `config/mapping.yaml` の `columns[].source` を修正。
   master列は「修了者マスタ」3行目ヘッダーの**改行・空白を除いた文字列**で指定します。
3. 値の対応が変わったら `config/code_map.yaml` の変換表を修正。
4. `pytest` を実行して回帰がないか確認。

---

## テスト

```powershell
C:/Users/iishi/.venvs/koshin/Scripts/python -m pytest -q
```

コード変換（区分・停止処分の逆転含む）／禁則文字／番号形式／日付（3か月後の前日・月末跨ぎ・
うるう年）／営業日計算／申請者番号重複分割／CSVバイト列（BOM・CRLF・末尾改行なし・
ヘッダー一致）を検証します。

---

## ディレクトリ構成

```
koshin/
├── app.py                  # Streamlit UI
├── config/                 # settings / mapping / code_map（YAML）
├── dips/                   # コアロジック（読込・変換・検証・出力・セルフテスト・履歴）
├── tests/                  # pytest
├── input/                  # dips_format.csv（公式雛形）※gitignore
├── docs/                   # 仕様書
├── requirements.txt
└── README.md
```
