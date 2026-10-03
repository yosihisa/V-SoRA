# 段階031：guardを保持したVDIF部分読取

- 作成日：2026-10-03
- 状態：参照実装・有限検証完了
- 比較元コミット：e944f7e

## 読者向け概要

長い記録の後方にある短区間を読むたび、先頭からFIR計算をやり直すと処理が遅くなります。今回は必要な直前のguardから読みます。同じ4局の後方0.3秒では相関結果が一致し、各局のdecoded frame数を1402から152へ減らせました。部分読取で飛ばした区間を検査済みとはしません。

## 1. 目的・対象範囲

固定長VDIFの部分seekとsample bufferへの接続。連続読取との相関一致、frame数・CPU比較。長session scheduler、未知時計/LOの追跡、GPU、実観測は対象外。

## 2. 完了条件

- 部分seekでglobal sample index/time/invalidを保持。
- 読取範囲のheader・timeの不整合を拒否し、未読prefixの限界を確認。
- FIR/補間の値・mask一致、後方区間の相関・重み・診断の一致。
- source/wheel・checkout外CLI/日本語GUI、記録・匿名監査・コミット。

## 3. 実際に行った作業

- `vdif.py`：start_sampleを追加。先頭headerの形式・局IDからframe長と公称時刻を求め、frameへ切り下げてseek。global sample indexを保持。物理file全長、読取中のheader/時刻連続性、invalidを検査。legacy EDVを許可せず、EDV0・8bit complex・1channel/threadに限定。
- `aligned.py`：最初のqueryに必要なsampleより64sample以上前のframeから開始。65tap FIRの履歴とradius32の65tap sinc補間supportを保持。decoded frame数・開始index・読取mode/検査範囲を記録。
- `__main__.py`：単独CLIに--sequential-inputを追加。prefixも先頭から検査したい場合に選ぶ。GUIは部分seek時の未読範囲を日本語で説明。
- VDIF・sample buffer試験、`guarded_seek_validation.py`、`verify_seek_installed.py`を追加。配布GUIの独立作業場所での後方解析を検証。時計・Closure入力規約を現制限へ更新。

## 4. 検証条件・結果

Python3.12.3、NumPy2.5.1、SciPy1.18.0、Astropy7.2.2、Baseband4.3.0、BLAS/OMP一thread。生成済み段階027の4局・3.04秒VDIF、1.42GHz、Fs2.048MHz、FFT32、既存rate profileを使用。一定LO/gain、点源・受信機Gaussian、実sample時計は正確な公称値を供給した模擬条件。

### 同一後方区間の相関

start2.502秒・画像積分0.3秒。従来相当のprefix連続読取とguard付きseekを別Python processで実行。相関・重み・time/RF/UVW・有効露光・power/SK/flag/countは全て一致（浮動配列の最大差0）。metaの読取方式・検査範囲は意図して異なる。

| 項目 | 先頭から読む | guard付き部分seek |
| --- | --- | --- |
| decoded frame／局 | 1402 | 152 |
| elapsed | 5.69秒 | 3.05秒 |
| process peak RSS | 227476KiB | 226840KiB |

一回のWSL計測でOS cacheは固定していない。順番は連続→seek。記憶装置のthroughputや実時間相関の達成を示すものではない。

### 30秒の部分query

frame15000個、論理123360000byte、疎fileの物理割当61440000byte。payloadはholeのzero byteからdecodeされる一定複素ADC値で、sky/受信機雑音ではない。29.5秒から8192sampleを小数位置0.35でquery。

| 項目 | 先頭から読む | guard付き部分seek |
| --- | --- | --- |
| decoded frame | 14753 | 4 |
| elapsed | 7.661秒 | 0.01778秒 |
| 値・invalid mask | 部分seekと一致 | 連続読取と一致 |

これはsample bufferのアルゴリズムとframe数の確認で、全観測pipelineがこの速度になるとはしない。原本全SHA計算の費用は別で、pipelineは引き続き全体を読む。

### 入力・配布・GUI

- frame切下げ、global index/時刻、invalid、範囲外/不正start、欠損でtarget時刻がずれる例、target局ID不一致、末尾切断を確認。
- prefixの未読headerだけを壊した例は、全読取で拒否・後方seekでは処理。飛ばした範囲を検査したことにしないという仕様を実例で確認。
- 整数/0.35/0.999位置、invalidの前後、複数queryでFIR値とmaskが一致。新しいtest生成式の初回に複素数へmoduloが適用されるTypeErrorがあり、実数部分のmoduloへ括弧を付け修正。読取実装はこの修正で変更せず。
- source157成功（39.38秒）、wheel157成功（38.91秒）、3544既知deprecation warning。pip check成功。
- checkout外のinstalled CLIをseek/sequentialの両方で実行し、参照相関と全数値配列一致。
- 配布GUIのChromium実操作：start1.502秒、pilot256×4ms=1.024秒、最終0.3秒の解析完了。部分seekの日本語説明・画像・総相対fluxを確認。独立一時作業場所で既存GUI履歴へ干渉せず、JS例外0、外部通信0、390px横溢れなし。RMLの全support比較も確認。

```bash
python tools/run.py workflows.guarded_seek_validation run --manifest outputs/stage027-three-second/input/manifest.json --clock-model outputs/stage027-three-second/input/clock.json --rate-profile outputs/stage027-three-second/pipeline/rate-only.json --output outputs/stage031-guarded-seek
python tools/run.py pytest -q
```

[結果と入力SHA](../../validation/runs/stage031/summary.json)、[CPU/frame比較](../../validation/runs/stage031/benchmark.png)、[checkout外CLI](../../validation/runs/stage031/installed.json)、[配布ブラウザ](../../validation/runs/stage031/browser.json)、[GUI画面](../../validation/runs/stage031/gui-screen.png)、[回帰/wheel識別](../../validation/runs/stage031/verification.json)。大きな疎VDIF/wheel/ログ/導出manifestはGit外outputs/stage031-*。

## 5. 制約・未解決事項

完全に閉じた固定長profileのfileを想定。飛ばしたprefixの全headerは検査せず、SHAは原本識別で構造正常性の証明ではない。nominal frame時刻の検査と実sample時計の正しさは別。現在は3秒/600m/100万cell以内の処理、線形sample時計を供給、一定LO profileの範囲外は拒否する。実記憶装置、連続時間、実機、非線形LO/時計、実Cas A形状の改善は未検証。

## 6. 次段階

同じ長記録から複数の短windowを処理する入口を作る。windowごとにrateを再推定し、その有効時間内のIQから相関・Closureを作り、露光と失敗位置を記録して合成へ接続する。window内の安定性と、window間のLO変化を区別して検証する。
