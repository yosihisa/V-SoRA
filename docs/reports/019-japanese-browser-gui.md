# 段階019：日本語ブラウザGUIの第一版

- 作成日：2026-10-02
- 状態：完了（模擬観測・検証・履歴）
- 比較元コミット：5dd1d9e

## 読者向け概要

コマンドを一つずつ入力しなくても、模擬天体・局配置・時間・雑音を選んで画像を作れる画面を追加しました。重要な検証を選び、処理中・完了・中止を区別し、画像と誤差を同じ画面で確認できます。

## 1. 目的・対象範囲

WSL Ubuntuの科学処理を日本語GUIから操作する。開発と観測者の操作の両方を扱いやすくし、第一版では模擬観測・RFI/時計/位相回転/基本検証・履歴を接続する。

## 2. 完了条件

ブラウザから点源生成→画像化、RFI検証、処理中止が動く。日本語表示・狭い画面・画像表示・結果保存を確認。入力拒否・履歴・checkout外wheelを検証。全回帰成功。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/`：FastAPI server、入力検査、直列の別process実行、状態のatomic保存、process group中止、再起動時の中断表示。
- HTML/CSS/JavaScriptで日本語画面。JavaScriptビルドなし。条件、数値、画像、保存ファイル、必要時の詳細ログ。
- 最初のChromium画像は日本語フォント不足で文字が四角く表示。Google公式公開Noto Sans JPをWOFF2へ変換し、OFLと出典SHA256を同梱して修正。外部CDNのruntime依存なし。
- `vsora-ui`入口、GUI optional依存、固定版、package-dataを追加。フォントは約4.35MB、wheel約5.40MB。
- `tools/verify_ui_browser.py`、API/科学subprocess/入力拒否/中止/履歴の試験と[操作ガイド](../guide/06-gui.md)を追加。
- 利用者の新しい前提を反映：実観測では高精度な局応答較正を必須にせず、Closure＋RMLを後続の主経路とする。ここでは未実装。

## 4. 検証条件・結果

```sh
.verification-venv/bin/python tools/run.py pytest -q
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser .verification-venv/bin/python tools/verify_ui_browser.py --output outputs/stage019-browser-validation
.verification-venv/bin/pip wheel . --no-deps -w outputs/stage019-wheel
.verification-venv/bin/python -m pytest -q
```

- sourceと再導入wheelで全回帰 **90件成功**。Baseband873件、Starlette/httpxの既知deprecation1件。
- Headless Chromium153.0.8010.12。日本語font loaded、JavaScript error0、外部request0。
- ブラウザのボタンから点源生成・画像化：処理完了、peak **1000Jy/beam**。画像2枚を読込み確認。
- 同じ画面でRFI検証：処理完了、相関誤差 **4.7688%**。
- 実処理の中止：cancelled。390pixel幅で横overflowなし。画像を目視確認し、日本語文字・入力・数値が読めることを確認。
- checkout外の新しい作業領域で導入済み`vsora-ui`を起動。font SHA256一致、point生成/画像化成功。checkoutなしの検証入口は無効。
- `pip check`で依存不整合なし。

[ブラウザ記録](../../validation/runs/stage019/browser-summary.json)、[点源結果画面](../../validation/runs/stage019/point-result-screen.png)、[模擬観測画面](../../validation/runs/stage019/simulation-screen.png)、[狭い画面](../../validation/runs/stage019/mobile-screen.png)、[wheel記録](../../validation/runs/stage019/wheel-summary.json)。大容量/実行ログはGit管理外`outputs/gui/`と`outputs/stage019-*`。

## 5. 制約・未解決事項

Windowsのブラウザ・WSLg desktopは直接観察していない。WSL内の実browser操作を確認。clock/fringe/basicの画面dispatchは登録済みで、ブラウザ実操作はpoint/RFI/cancelを対象とした。複数server同時起動のworkspace排他、実入力一覧、Closure/RML、長時間運用は後続。現在の模擬観測は仮想地点・理想visibilityで、実装置の高精度較正を確認したものではない。

## 6. 次段階

Closureの局利得不変性、雑音共分散、短積分とLO差による相関損失を実装・検証する。Closure＋RMLを実観測の主経路として文書・GUIへ追加する。
