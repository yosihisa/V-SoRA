# 段階036：pilot内の分割rate診断

- 作成日：2026-10-03
- 状態：完了（下記の有限模擬条件・ソフト検証の範囲）
- 比較元コミット：c590c4f

## 読者向け概要

一つのpilotを4部分へ分け、それぞれで局周波数差を推定します。雑音から予想する差より大きく変わると、一定rateの仮定を疑います。短い部分で信号を測れない場合は未判定です。分割した平均rateが整合しても、不規則な位相変動がないことを証明した値ではありません。日本語GUIで診断を表示し、必要なら画像化前に停止できます。

## 1. 目的・対象範囲・完了条件

目的は、段階035で見つかった「一定rate処理が完了しても積分中の変動が残る」問題を診断として記録することです。一定rate・滑らかな変動・情報不足を区別し、CLI・GUI・単一区間・区間列の停止を検証します。位相曲率の自動補正は次段階です。

完了条件は、有限模擬試験と保存pilot、実VDIF処理の再現、source/wheelの全テスト、インストール済みCLI、実Chromium、日本語ドキュメント、公開前確認と匿名コミットです。下記の範囲で実施しました。

## 2. 実際に行った作業・変更ファイル

- `rate.py` のpilot配列確認を共通化し、`rate_variation.py` に4分割診断と `vsora-rate-diagnose` を追加。
- 各部分は8時刻以上、既存の未知sky/gain rate solverを使用。局間共分散も保存します。部分同士の局rate差を近似誤差で規格化し、最大値が6を超えると変動検出です。どれかが解けない場合は未判定です。
- `closure_pipeline.py` と `sequence.py` に診断保存・集計・必須指定を追加。初期値は診断のみ。`--require-rate-consistency` では変動検出・未判定をpilot後に停止します。
- UIの `models.py`、`worker.py`、`static/app.js`、`static/index.html` に日本語の3状態、4部分の図と表、必須指定、失敗時の診断表示を追加。
- correlator/UI tests、`workflows/rate_variation_validation.py`、独立CLI/browser確認ツール、guide06/07、interface、記録を追加。

診断のみで相関値やweightを自動修正しません。必須指定は近似条件の確認で、実機coherenceの保証ではありません。

## 3. 検証条件・結果

### 有限の数学的visibility試験

4局、8channel、4ms刻み、各基線/channelの未知定数、各実部・虚部に独立Gaussian雑音を与えました。これは条件付きvisibilityモデルで、物理IQ・実機測定ではありません。

| 仮定条件 | 整合 | 変動検出 | 未判定 |
| --- | ---: | ---: | ---: |
| 一定rate、64乱数seed | 60 | 0 | 4 |
| 局rate傾き[0,2,-1,3]Hz/s、16seed | 0 | 16 | 0 |

当初の単体テストは一定rateの全例を整合と期待して1件失敗しました。短い部分の局rate graphが雑音で不整合となる例を未判定として保ち、期待値を修正しました。推定側の採用境界を緩めていません。有限例の件数から実機の偽検出率を推定した結果ではありません。

### 平均rateでは見逃す例

4部分の各々に同じ1周期のcos位相変動を入れると、部分の平均rateは整合しました。仮定位相振幅[0,0.2,-0.3,0.5]radでは、最大基線差0.8radのcoherenceは計算上J0(0.8)=0.84629です。周期平均とBessel関数の関係は[NIST DLMF 10.9](https://dlmf.nist.gov/10.9)の積分表現に対応します。これは計算した反例で、実機で15%減衰を測った結果ではありません。

### 段階035の保存済み物理IQ→VDIF pilot

入力SHAを確認して同じpilotを診断しました。4局・点源・仮定SEFD10000Jy・一つの乱数seed・既知の線形ADC時計を使った模擬記録です。生成rate傾きを推定へ与えていません。

| 条件 | 診断 | 最大rate差/近似誤差 |
| --- | --- | ---: |
| 変動なし・3秒pilot | 整合 | 3.06 |
| 変動なし・0.512秒pilot | 整合 | 1.54 |
| 中程度・3秒pilot | 変動検出 | 46.20 |
| 強い変動・3秒pilot | 変動検出 | 452.71 |
| 強い変動・0.512秒pilot | 変動検出 | 6.26 |

短いpilotでも変動検出となった最後の条件は、段階035の0.3秒相関では減衰約1%でした。変動の検出と、減衰の許容量は違う評価です。

同じ中程度VDIFを診断のみで再相関し、段階035のvisibility・weight・UVW・時刻・周波数・露光・power/SK・整数diagnosticsと比較して全配列差0でした。必須指定ではpilotだけを完了し、最終相関と画像を作らず未完了記録を残しました。

### source・wheel・CLI・ブラウザ

- ソース版204件成功、警告17192件、134.28秒。
- インストール版204件成功、同警告、135.16秒。pip check成功。
- wheel 5,445,857bytes、SHA256 `100676bde7845ee48fa5e37d1d06e48e69a9a310c7f65f9fc2df98251ab37b96`。
- インストール済み診断CLIをcheckout外で5pilotへ実行し、同診断を再現。必須指定CLIも画像化前に停止。
- Chromium 153で診断のみのRML完了、必須指定の停止、3区間列の整合集計、区間列の最初の変動停止、日本語フォント、画像、390px表示を実操作。JS error0、外部request0、横はみ出しなし。
- 必須区間列試験は第1区間で停止する指定の転送・失敗位置確認です。記録が予定2区間全体を覆う試験ではありません。
- GUIのRML試験は1初期値・100反復で上限。処理/UI確認で、画像品質の合格判定ではありません。

警告は既存Baseband/NumPy shapeとStarlette TestClient等です。警告ゼロの検証ではありません。Windowsブラウザ、WSLg、RTL-SDR実機は未検証です。

## 4. 再実行・記録

```bash
python tools/run.py workflows.rate_variation_validation --reference-run outputs/stage035-drift --output outputs/new-rate-diagnostic
vsora-rate-diagnose --input outputs/stage035-drift/moderate-3s/pilot/shard-00000.npz --output outputs/new-diagnosis.json
python tools/verify_rate_diagnostic_installed.py --reference-run outputs/stage035-drift --output outputs/new-installed-diagnostic
```

凍結した段階035の原本が必要です。大きなIQと実行ログはGit外 `outputs/stage035-drift/`、`outputs/stage036-diagnostic/`、`outputs/stage036-browser/`、`outputs/stage036-installed-cli/`、`outputs/stage036-verification/` に保存。公開記録は [数値と入力SHA](../../validation/runs/stage036/diagnostic.json)、[CLI](../../validation/runs/stage036/installed-cli.json)、[browser](../../validation/runs/stage036/browser.json)、[wheel/tests](../../validation/runs/stage036/verification.json)、[停止画面](../../validation/runs/stage036/required-stop.png)です。

## 5. 制約・未解決事項

Fisher Gaussian独立雑音近似と一定sky/gainを使います。6σ最大差の多重比較・相関雑音・未知RFIに対する偽検出確率は未評価。部分内の速い位相変動、alias、共通rate、実機安定性、弱いCas A信号をこれだけで決められません。短い部分で信号が弱くなる問題も残ります。実観測・拡がったCas Aの画像忠実度・変動の自動補正は実施していません。

## 6. 次段階

測れた部分rateから滑らかな変動モデルを推定し、平均前のIQへ適用する処理と、適用条件・偏り・Closure回復を検証します。
