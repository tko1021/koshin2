# クラウド版 デプロイ手順（Streamlit Community Cloud）

このアプリ（`cloud/app.py`）を Streamlit Community Cloud に公開し、スタッフが
ブラウザ＋パスワードで使えるようにする手順です。

> ⚠️ **GitHubリポジトリは必ず「Private（非公開）」にしてください。**
> `assets/印影.png`（機関の印影）を含むため。個人情報や鍵（secrets/）はコミットされません。

---

## 0. 前提
- GitHubアカウント（取得済み）
- データ用Googleシート `koshin_master` … サービスアカウント
  `koshin-sheets@koshin-dips-0188.iam.gserviceaccount.com` に編集者共有済み（設定済み）
- Streamlit用Secretsの内容 … `secrets/streamlit_secrets.toml` に生成済み

## 1. GitHubに非公開リポジトリを作成してpush
このリポジトリ（`C:\Users\iishi\Documents\koshin`）を、GitHubの**Privateリポジトリ**にpushします。
（コマンドは別途案内します。`gh` CLI があれば自動化できます）

## 2. Streamlit Community Cloud でデプロイ
1. https://share.streamlit.io/ を開き、**GitHubでサインイン**
2. 「New app」→ リポジトリを選択
3. **Branch**: main（または master）
4. **Main file path**: `cloud/app.py`　← ここが重要
5. 「Advanced settings」→ **Python version**: 3.11 以上を選択
6. 「Deploy」

## 3. Secrets を設定
1. デプロイ後、アプリの「⋮」→「Settings」→「Secrets」
2. ローカルの **`secrets/streamlit_secrets.toml` の中身をすべてコピー**して貼り付け
3. `app_password` を**スタッフ用の実パスワード**に変更
4. 保存（アプリが自動で再起動）

## 4. 動作確認
- 公開URLを開く → パスワード入力 → ログイン
- 「修了者を登録」で1件登録 → 「DIPS_CSV作成」「修了証明書発行」で出力できるか確認

## 5. スタッフへ共有
- 公開URL と パスワード を伝える
- 使い方はアプリ内「操作マニュアル」ページ

---

## 補足
- データはGoogleシート（`修了者マスタ`／`発行履歴`タブ）に保存されます
- ローカル版（master.xlsx）は従来どおりこのPCで使えます（クラウドとは別データ）
- コード更新時：GitHubにpushすると Streamlit Cloud が自動で再デプロイします
