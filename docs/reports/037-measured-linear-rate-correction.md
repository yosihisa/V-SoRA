# 段階037：測定した滑らかな周波数変動のIQ補正

- 作成日：2026-10-03
- 状態：完了（有限模擬条件とCLIの範囲）
- 比較元コミット：162edfa

## 読者向け概要

周波数差が一定なら、位相は直線的に回転します。周波数差が時間に比例して変わるなら、位相は二次曲線になります。pilotを4分割して測った局周波数差からその傾きを求め、相関で平均する前のIQへ補正を適用しました。生成した正解の傾きを補正へ渡していません。

3秒の点源模擬VDIFでは、一定モデルで残った減衰やClosure偏りを減らせました。高速な位相の揺れや実機の安定性まで測れる機能ではありません。現在はCLI・単一区間が対象です。

## 1. 目的・対象範囲・完了条件

段階035で残った滑らかなLO変動を、段階036の分割測定から補正します。未知sky/gain、相対局rate、従来の一定モデルを維持し、線形モデルを明示的に選ぶ入口を追加しました。完了条件は、全局共分散・情報不足・モデル不整合・範囲外の扱い、同じ物理IQ→VDIFでのClosure比較、source/wheel回帰、インストール済み独立CLI、記録・匿名コミットです。

GUIと複数区間のモデル選択、実機、確率的位相雑音、弱いCas Aの画像忠実度は後続課題です。

## 2. 実際の作業・変更ファイル

- `rate_linear.py`：4部分の局rateと局間共分散を使うweighted least squares。相対rateと傾き、全パラメータ共分散、近似reduced χ²を保存。
- `aligned.py`：queryした電圧のphysical timeに二次位相を適用。`rate_applied_slopes_hz_per_s` とprofile typeを保存。
- `closure_pipeline.py`：`--rate-model constant/linear`、`rate-linear.json`。初期値はconstant。
- `rate.py`：線形補正済みpilotに定数の残差だけを重ねたprofileを作らないよう拒否。
- `pyproject.toml`：`vsora-rate-linear` を追加。
- `test_rate_linear.py`、`workflows/linear_rate_validation.py`、`tools/verify_linear_installed.py`、guide07、interface、公開記録を追加。

位相補正は `2π * (r * τ + 0.5 * a * τ²)` radです。rはprofile基準時刻のHz、aはHz/s、τはそこからの秒。各局のIQから除いてから平均します。幾何補正は従来どおりです。位相の定数項は未知局gainに残り、Closureでは消えます。

各部分が解けること、線形モデルreduced χ²≤3、全基線の予測endpoint rateが指定範囲内、推定傾きによる各部分の中心化coherence計算が90%以上であることを確認します。最後の値は局所の一定rate推定を使うための計算上の制限で、相関の実測保持率ではありません。線形profileの範囲外延長は拒否します。

`--require-rate-consistency` は「一定rateが整合すること」を要求するため、線形補正との同時指定を拒否します。線形モデル自身の適合確認は常に行います。

## 3. 検証条件・結果

### 単体検証

局間共分散を含む正確な線形データ、未知のchannel複素visibility、情報不足、非線形な部分rate、非正定値共分散、適用範囲・局順・Nyquist・傾きの値、補正済みpilot拒否、設定の矛盾を7テストで確認しました。部分内の周期位相変動は、線形モデルでも見逃すことを確認し、`coherence_stability_measured=false` を保存します。

### 物理IQ→VDIFの3秒相関

段階035の凍結原本を再使用しました。4局、1.42GHz、2.048Msample/s、点源、仮定SEFD10000Jy、固定の未知局gain、同じ雑音seed35、正確な公称線形ADC時計です。2ms×1500のpilotから推定し、3秒の画像用相関へ適用しました。生成傾きは比較だけに使いました。

| 生成条件 | 最大傾き誤差 Hz/s | 最小振幅比（対照比） | Closure phase RMS rad | Closure log amplitude RMS |
| --- | ---: | ---: | ---: | ---: |
| 変動なし | 0.002488 | 0.999455 | 0.02764 | 0.03274 |
| 中程度 [0,.1,-.05,.15]Hz/s | 0.002625 | 0.999325 | 0.02761 | 0.03275 |
| 強い変動 [0,1,-.5,1.5]Hz/s | 0.002622 | 0.999347 | 0.02764 | 0.03270 |

全例のprofile基準時刻における最大rate誤差は0.00404Hz以内。近似model reduced χ²は2.72〜2.77でした。noise仮定が完全に校正された結果とは扱いません。

中程度の一定rate処理では最小振幅比0.9171、Closure log amplitude RMS0.07774だったため、この有限条件で減衰と偏りが縮小しました。強い変動の一定rate処理はglobal rate graphが不整合で停止しましたが、局所推定から作る線形モデルでは3秒相関まで完了しました。

振幅比は同じ雑音生成・sky・gainの変動なし記録との比較で、未知skyの実観測から直接得られる量ではありません。生成傾きと測定傾きの差を入れたcoherence計算も比較用です。RML画像はこの段階では作っていません。点源のClosure回復をCas A画像の忠実度に置き換えません。

### source・wheel・CLI

- source211件成功、警告18272件、146.39秒。
- installed wheel211件成功、同警告、144.96秒。pip check成功。
- wheel 5,449,155bytes、SHA256 `5e0cba0be8d58b1c2bc84088126e373f95b0b5d4dae8aea944e9332f03f2cbe4`。
- checkout外のインストール済み `vsora-rate-linear` で中程度pilotのprofileを再現。
- 同じ独立CLIの単一区間pipelineで強い変動VDIFを処理し、sourceの全visibility/weight/UVW/time/frequency/露光/power/SK/整数diagnostics配列と一致。

警告は既存Baseband/NumPy等のdeprecationです。Windows、WSLg、実機の検証はありません。

## 4. 再実行・検証記録

```bash
python tools/run.py workflows.linear_rate_validation --reference-run outputs/stage035-drift --output outputs/new-linear-validation
vsora-rate-linear --input outputs/stage035-drift/moderate-3s/pilot/shard-00000.npz --output outputs/new-linear.json
python tools/verify_linear_installed.py --reference-run outputs/stage035-drift --source-run outputs/stage037-linear --output outputs/new-installed-linear
```

同じ凍結原本が必要です。大容量原本とログはGit外 `outputs/stage035-drift/`、`outputs/stage037-linear/`、`outputs/stage037-installed-cli/`、`outputs/stage037-verification/`。公開の [数値・pilot SHA・モデル](../../validation/runs/stage037/summary.json)、[CLI](../../validation/runs/stage037/installed-cli.json)、[tests/wheel](../../validation/runs/stage037/verification.json)、[図](../../validation/runs/stage037/correction.png)を参照してください。

## 5. 制約・未解決事項

4部分の近似Gaussian Fisher誤差を独立として使います。filtered FFT、共有sky、RFIなどの相関とモデル選択の偽検出率は未校正。各部分で信号を検出できる感度が必要です。部分内の周期的位相変動、alias、共通局rate、非線形ADC時計、変動sky/gainをこの線形モデルだけで復元できません。

原本一seed・4局・点源・仮定した滑らかな傾きの結果です。実OCXOの安定時間、低SNR Cas Aの画像、絶対flux/位置、連続長時間処理の実用性能は未確定です。形状が戻る見込みを積み上げる段階であり、実観測用ソフト完成の宣言ではありません。

## 6. 次段階

日本語GUIと区間列のモデル選択・適合値・傾き表示を追加します。その後、非線形変動と低SNRでの失敗範囲を広げ、実機条件の入力と観測計画を確認します。
