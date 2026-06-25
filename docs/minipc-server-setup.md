# ミニPC社内サーバー構築 手順書

ミニPC（NUCBOX_M6ULTRA）をWindowsのままSSHサーバー化し、Claude Code・git・GitHub CLI を導入、全プロジェクトを集約するための記録。別PC（MSI）からリモート開発できる状態を構築済み。

---

## 環境・基本情報

| 項目 | 値 |
|---|---|
| サーバー機（ホスト名） | NUCBOX_M6ULTRA |
| サーバーOS | Windows 11（Version 10.0.26100） |
| サーバーのユーザー名 | `takao` |
| サーバーのIP（Wi-Fi） | `192.168.1.3` ※未固定。要DHCP予約 |
| 接続元PC | MSI（ユーザー名 `iishi`） |
| GitHubユーザー | `tko1021` |
| git設定 | name: `Takao` / email: `seinodrone@gmail.com` |
| プロジェクト置き場 | `C:\Users\takao\projects` |
| Claude Code | v2.1.187（モデル Opus 4.8）/ `C:\Users\takao\.local\bin` |
| SSH既定シェル | `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` |

---

## 日常の使い方（これだけ覚えればOK）

接続元PC（MSI等）のターミナルで:

```
ssh takao@192.168.1.3
```

- 鍵認証済みのため **パスワード不要**
- 既定シェル設定済みのため **入った瞬間からPowerShell**（`powershell` と打つ必要なし）

プロジェクトで作業する例:

```powershell
cd C:\Users\takao\projects\koshin
claude
```

抜けるときは `exit`。

---

## 構築手順（実施済みの記録）

### 1. OpenSSHサーバーの導入（サーバー機・管理者PowerShell）

管理者PowerShellを開く（スタート右クリック →「ターミナル(管理者)」）。

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
Get-Service sshd          # Status: Running を確認
```

ファイアウォールで22番ポートを開放:

```powershell
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

IP確認:

```powershell
ipconfig          # Wi-FiのIPv4アドレス = 192.168.1.3
```

### 2. Claude Code の導入（サーバー機・PowerShell、管理者不要）

```powershell
irm https://claude.ai/install.ps1 | iex
```

PATHに通っていない警告が出た場合は登録:

```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:USERPROFILE\.local\bin", "User")
$env:Path += ";$env:USERPROFILE\.local\bin"   # 今のセッションにも即反映
claude --version                               # 2.1.187 を確認
```

初回起動でブラウザ認証（SSH越しの場合は表示URLを手元ブラウザで開く）:

```powershell
claude
```

### 3. git / GitHub CLI の導入（サーバー機・PowerShell）

```powershell
winget install --id Git.Git -e --source winget
winget install --id GitHub.cli -e --source winget
```

> winget導入後はPATH反映のため一度SSHを抜けて入り直す。

git初期設定:

```powershell
git config --global user.name "Takao"
git config --global user.email "seinodrone@gmail.com"
```

GitHubログイン（ブラウザ認証）:

```powershell
gh auth login
# GitHub.com → HTTPS → Yes → Login with a web browser
# 表示された8桁コードを https://github.com/login/device に入力
```

### 4. リポジトリの集約（サーバー機）

```powershell
mkdir C:\Users\takao\projects
cd C:\Users\takao\projects
gh repo clone tko1021/koshin
```

> 一覧確認は `gh repo list`。

### 5. SSH鍵認証（パスワードなし接続）

**接続元PC（MSI）で鍵を作成:**

```powershell
ssh-keygen -t ed25519          # 3回の質問は全てEnter（保存先デフォルト・パスフレーズ空）
type $env:USERPROFILE\.ssh\id_ed25519.pub    # 公開鍵を表示してコピー
```

**サーバー機（takao = 管理者アカウント）で公開鍵を登録:**

> ⚠ 重要: 管理者アカウントの場合、OpenSSHは各ユーザーの `.ssh\authorized_keys` ではなく
> `C:\ProgramData\ssh\administrators_authorized_keys` を参照する。ここに登録しないと効かない。

```powershell
echo （コピーした公開鍵） >> C:\ProgramData\ssh\administrators_authorized_keys
icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```

### 6. SSH既定シェルをPowerShellに（サーバー機）

> SSHで入ると既定ではCMDに降りる。毎回 `powershell` と打つ手間をなくす設定。
> このミニPCには PowerShell 7（pwsh）が未導入のため、標準の powershell.exe を指定。

```powershell
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
```

> 設定後はSSH接続が壊れる可能性に備え、**今のセッションは閉じず**、別ターミナルから接続テストして確認すること。
> 戻したい場合: `Remove-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell`

### 7. スリープ無効化（サーバー機）

> 放置でスリープに入ると接続がタイムアウトするため無効化。

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

---

## 躓きポイント集（再発防止メモ）

- **CMDとPowerShellの取り違え**: プロンプト先頭に `PS` が付くのがPowerShell。`irm ... | iex` や多くの設定コマンドはPowerShell専用。`#` で始まる行はコメントなので実行不要。
- **管理者権限不足**: `Add-WindowsCapability` 等で「要求された操作には管理者特権が必要です」→ 管理者でPowerShellを開き直す。管理者窓は初期位置が `C:\windows\system32`。
- **コピペで行がくっつく/プロンプトが混入**: 複数行をまとめて貼ると `xxxcd` のように連結する。1行ずつ貼る、迷ったら手打ち。プロンプト文字（`takao@...>`）はコピーしない。
- **鍵を入れたのにパスワードを聞かれる**: 管理者アカウントは `administrators_authorized_keys` を使う（上記5参照）。
- **既定シェルのパスが存在しない**: `where.exe pwsh` で実在確認してから指定。無ければ標準 `powershell.exe` を使う。
- **急にタイムアウト**: ミニPCがスリープした可能性。本体を起こす／スリープ無効化（上記7）。IPが変わった可能性も `ipconfig` で確認。
- **gh の認証情報が平文保存の警告**: 専用資格情報マネージャーが無い環境の通常動作。ミニPC自体を信頼できる前提なら実用上問題なし。

---

## 残タスク（任意・後日）

- [ ] **IP固定化**: ルーターのDHCP予約で `192.168.1.3` をこのミニPCに固定（番号ズレ防止）
- [ ] **他リポジトリの集約**: `gh repo list` で確認し、必要なものを `projects` に `gh repo clone`
- [ ] **VS Code Remote-SSH**: 黒い画面でなくVS CodeでミニPC上のコードを直接編集したい場合に設定
- [ ] **PowerShell 7 導入（任意）**: `winget install Microsoft.PowerShell` を入れる場合、既定シェルを pwsh パスに更新
