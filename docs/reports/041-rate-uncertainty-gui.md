# 段階041：推定誤差診断の日本語GUI

- 作成日：2026-10-03
- 状態：完了（日本語GUI・条件付き計算・模擬入力の範囲）
- 比較元コミット：510a400

## 読者向け概要

周波数差の推定誤差から計算した予測値を、通常の解析結果の中で確認できるようにします。計算の仮定と実機で未確認の事項を数値の近くに表示します。

## 1. 目的・対象範囲

線形rateを選んだVDIF解析と短区間列で、各画像積分の条件付き複素coherenceを表示します。Gaussian誤差の計算検証を動作検証メニューへ追加します。周期位相検証でも、推定誤差の診断とモデル外の減衰を区別します。

## 2. 完了条件

実API・installed CLI/GUI・Chromiumの画面で診断と説明が一致すること。日本語font・390px幅・外部request/JS errorを確認すること。source/wheel全回帰、レポート、匿名コミットを完成させること。

## 3. 実際の作業

- `static/app.js`：単区間・区間列の線形モデルに条件付き予測を表示。最小値、画像積分範囲、基線ごとの予測と両端の位相σ、Gaussian・一様露光の仮定、欠損mask/速い揺れを含まないことを表示。古い記録に診断がない場合も表示。
- `models.py`、`jobs.py`、`worker.py`、`static/index.html`：動作検証のGaussian計算メニュー、説明・表・図。周期位相検証にも該当行の診断を表示。
- `workflows/rate_uncertainty_validation.py`：アーカイブを指定しないときは空の比較パネルを作らず、Gaussian比較の1枚だけを描画。
- UI tests、`tools/verify_linear_ui.py`、`tools/verify_periodic_ui.py`、`tools/verify_uncertainty_ui.py`、guide06、相関pipelineのinterface説明、小容量の公開記録。

productionの補正・相関・RMLアルゴリズムは段階040と同じです。実ブラウザ検証ではインストール済みGUIを使い、動作検証だけは明示的にcheckout側のworkflowを呼びました。wheel単独ではcheckoutの検証workflowを実行できません。

## 4. 検証条件・結果

### APIと実Chromium

- 実APIのGaussian検証と線形区間列：対象2件成功、29.74秒、警告3201件。
- 単区間：段階039の速い周期位相を含むVDIFを、線形rate・pilot2ms×1500・画像3秒・RML1初期値100反復で解析。条件付き予測99.9821%と前提を表示。RML χ²/測定数0.738874ですが反復上限で、画像品質の合格ではありません。
- 区間列：段階038の同一VDIFから3窓、各pilot0.512秒・画像0.3秒。各窓の診断3個を表示。RML χ²/測定数0.942065、1初期値100反復で上限到達。
- 未判定：16個pilot・刻み0.016秒・画像0.1秒・探索25Hzでは、4部分の推定不足を日本語で表示して停止。画像を完成扱いにしないことを確認。
- Gaussian：実メニューから65536標本・6基線の計算を実行。数式の複素平均、標本の複素平均の実部、標本の振幅平均を別列に表示。実機と推定器の共分散の検証ではないことを確認。
- 周期位相：対照・速い/遅い周期のIQ→VDIFをメニューから再生成。速い周期・線形rateの条件付き予測99.9821%と、対照振幅比84.59%を同じ行に表示。遅い周期の相関は未完了として表示。
- Chromium153.0.8010.12、日本語font成功、JS error0・外部request0。390px幅で単区間列・フォーム・Gaussian・周期位相の横はみ出しなし。

Windowsブラウザ・WSLg・実観測は未検証です。全ツールは独立した一時workspaceを使い、メインGUIの履歴を汚しません。メインlocalhost:8765は実行中ジョブ0を再確認して更新し、environment APIの応答を確認しました。

### 全回帰・配布

- source全回帰250件成功、警告22672件、394.11秒。
- installed全回帰250件成功、警告22672件、399.70秒。
- source/wheelは順番に実行。pip check成功。既存のBaseband/NumPy、Starlette等のdeprecation警告を含みます。

wheel 5455199bytes、SHA256 `74e46d2ea18ed8b39835129f7344fd713270eae468d3bde50a55f0a737986ef3`。

### 記録・再実行

大容量の原本・履歴・ログはGit外`outputs/stage041-*/`です。公開の[単区間・区間列・未判定](../../validation/runs/stage041/linear-browser.json)、[周期位相](../../validation/runs/stage041/periodic-browser.json)、[Gaussian](../../validation/runs/stage041/gaussian-browser.json)、[解析画面](../../validation/runs/stage041/analysis.png)、[区間列](../../validation/runs/stage041/sequence.png)、[周期位相画面](../../validation/runs/stage041/periodic.png)、[Gaussian小画面](../../validation/runs/stage041/gaussian.png)を参照してください。

[全回帰とwheelの識別情報](../../validation/runs/stage041/verification.json)も保存しました。

```bash
python tools/verify_linear_ui.py --manifest outputs/stage039-periodic/fast-input/manifest.json --clock-model outputs/stage039-periodic/fast-input/clock.json --sequence-manifest outputs/stage038-sequence/input/manifest.json --sequence-clock outputs/stage038-sequence/input/clock.json --output outputs/new-linear-gui
python tools/verify_periodic_ui.py --output outputs/new-periodic-gui
python tools/verify_uncertainty_ui.py --output outputs/new-gaussian-gui
```

インストール済みv-sora、Playwright/Chromium、checkoutが必要です。1番目は保存原本、2番目は数百MBの模擬原本を生成、3番目はGaussian計算だけを使います。

## 5. 制約・未解決事項

仮定Gaussian誤差・一様露光の条件付き診断です。実OCXOの保持率・信頼区間・画像品質の保証は対象外です。動作検証workflowにはcheckoutが必要です。

## 6. 次段階

推定器のFisher共分散と実際の推定誤差が対応するかを、有限の模擬雑音条件で調べます。
