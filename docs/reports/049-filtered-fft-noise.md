# 段階049：FIR・補間後のFFT雑音

- 作成日：2026-10-04
- 状態：完了（既知の固定Gaussianモデルの範囲）
- 比較元コミット：743d10e

## 読者向け概要

FFTを重ねずに区切っても、FIRや補間が前後の電圧を使うため、隣のFFTの雑音が関係する場合があります。既知のGaussian入力と固定した線形係数を使い、その関係を計算・検証しました。局別の係数では、基線間の雑音関係も変わり、FFT数を一つの数へ換算するだけでは表せない例があります。

## 1. 目的・対象範囲

既知の局共分散と局別の線形係数から、時刻間の相関を保持したvisibilityの全実共分散を計算します。現在のFIR・固定小数offsetの補間・FFTを係数へまとめ、実装と照合します。実機の有効独立数を測る処理は対象外です。

## 2. 完了条件

独立時刻の極限、共通係数の分散倍率、局別係数の交差共分散、既存補間との数値一致を確認すること。Gaussian電圧のMonte Carloで理論の全共分散を照合し、source/wheel全回帰・配布API・レポート・匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/simulator/src/vsora_simulator/filtered_noise.py`：既知の時刻間で独立な局電圧と、各局の有限係数から時刻差ごとの局共分散を計算。visibility平均の複素共分散・擬共分散・全実共分散へ伝播。2〜8局、固定stride、有限平均区間。
- `aligned_fft_kernel`：等しいsample rateの65tap Kaiser FIR・固定offsetの65tap sinc・矩形unitary FFTを一組の係数にまとめる。既存相関器の計算を変更せず、係数と直接処理を照合。
- `apps/simulator/tests/test_filtered_noise.py`：独立極限、長い移動平均、局別整数ずれ、実FIR/補間/FFT、複素局gain変換、不正入力、実Gaussian電圧、workflowを確認。
- `workflows/filtered_noise_validation.py`：6モデル・各8192試行。batch64でraw Gaussian電圧を生成し、局の共分散を与え、固定係数のconvolutionからFFT相当出力を作ってvisibilityを平均。基線選別なし。
- `tools/verify_filtered_noise_installed.py`：[式と規約](../../interfaces/filtered-visibility-noise.md)、[学部生向け説明](../guide/07-closure-rml.md)、小容量結果を追加。

局の電圧をy_i[a]、局間の時刻差dの共分散をR_ik(d)とすると、visibility雑音のΓとΠは各時刻対のGaussian4次モーメントを足し、M²で割ったものです。各差dの組数はM−|d|。式は[規約](../../interfaces/filtered-visibility-noise.md)に記載しました。visibility自体の分布をGaussianと仮定しない、入力モデルの下での正確な2次モーメントです。

全局の係数が同じ場合は、独立時刻の比較共分散に倍率ηを掛けられ、モデル上の換算数M/ηを返します。局別係数は単一換算を仮定せずnullにします。このAPIは実測した有効FFT数を返す推定器ではありません。

## 4. 検証条件・結果

### 対象試験・直接実装

最終対象35件成功、1.21秒。4条件の既存FIR→sinc→FFTと係数の直接積を、rtol/atol1e−12で照合しました。独立の矩形FFTでは段階042の式へ一致。長い共通移動平均の解析式、局別の整数ずれによる交差雑音、複素局gainの回転・振幅変換も一致。

局別整数ずれの3局モデルでは、平均visibilityは0、独立時刻を仮定した基線間共分散も0ですが、時間差を保持すると、8平均の場合の一つの複素交差共分散が7/64になりました。分散だけに共通係数を掛けても、この交差関係は作れません。

### 6条件・Gaussian電圧

各8192試行、seed49〜54。基準4局は共通成分1、複素位相[0,0.4,1.1,2.2]radの第二成分0.7、局別受信機雑音1.5。真の局共分散は既知で、推定器の実験ではありません。最後の整数ずれモデルは3局の共通成分1と局別雑音1。

| モデル | 公称出力数 | 理論の対角分散 / 独立時刻仮定 | 共通係数の場合のモデル換算数 | MC全共分散の最大規格化差 |
| --- | ---: | ---: | ---: | ---: |
| 現在のFIR/sinc・FFT8・中央 | 128 | 1.000138 | 127.9823 | 0.028967 |
| 現在のFIR/sinc・FFT32・中央・offset0.25 | 128 | 1.000015 | 127.9981 | 0.034101 |
| 現在のFIR/sinc・FFT32・Fs/4・offset0.25 | 128 | 1.000123 | 127.9843 | 0.027639 |
| 現在のFIR/sinc・FFT8・Fs/4・局別offset | 128 | 1.000582〜1.001526 | 単一換算を仮定しない | 0.045671 |
| 説明用の65sample移動平均・stride8 | 128 | 5.372648 | 23.8244 | 0.025924 |
| 説明用の局別整数ずれ・stride1 | 16 | 1.000000 | 単一換算を仮定しない | 0.035992 |

基準FIRはcutoff0.35Fs・Kaiser8.6、sincはradius32、FFTはnonoverlap。局別offsetは[0,0.25,0.5,0.75]sample。モデルFsは等しく、0.25FsはFs2.048MHzならbaseband512kHzです。説明用の後2モデルは現在の整列フィルターを使った実験ではありません。

規格化差は行・列の真の分散の平方根の積で割ったものです。全6条件で、全共分散要素と平均visibilityが、事前に定めた6 Monte Carlo標準誤差＋丸め許容内でした。分散倍率の小さい差をMonte Carloから精密に測れたという結果ではありません。

整数ずれの例は対角分散比が1でも、全共分散では独立時刻仮定から規格化最大0.234375の差がありました。共通移動平均は0.813872。対角の分散だけでなく基線間・実部虚部の雑音関係も比較しました。

### リソース・全回帰・配布

最終workflowを`/usr/bin/time -v`で測定：wall16.34秒、user13.60秒、system1.92秒、最大RSS204596KiB（約199.8MiB）、exit0。OPENBLAS/OMP各1thread、CPUによる一回の測定で、専用計算機の性能保証ではありません。rawの大量標本はbatch64ごとに破棄し、全標本をファイルへ保存しません。

source全回帰400件成功、警告23312件、406.67秒。図の目視で縦ラベルの見切れを見つけ、figureの高さとラベルを修正し、対象35件と同じseedの全6条件を再実行しました。共分散の計算・合否条件は変更していません。

installed APIはcheckout外で確認。3局整数ずれの7/64、長い共通移動平均の倍率5.372647929・モデル換算数23.82437891と解析式が一致。FIR/sinc/FFT係数の直接実装との差は最大2.94e−15でした。pip check成功。installed全回帰400件成功、警告23312件、404.66秒。source・installed API・installed全回帰を順に実施しました。試験除外なし。既存のBaseband/NumPy・Starlette等のdeprecation警告を含みます。

wheel5470832bytes、SHA256 `ad40f9294d470d24939bc45f8c41b98cbea952c98b1f37eccdc624c29daaf4c1`。

[モデル・集計](../../validation/runs/stage049/summary.json)、[分散と共分散比較の図](../../validation/runs/stage049/filtered-noise.png)、[installed API](../../validation/runs/stage049/installed-api.json)、[回帰とリソース](../../validation/runs/stage049/verification.json)を保存。完全ログ・wheel・途中の図はGit外`outputs/stage049-*/`です。図は最終版を目視確認しました。

```bash
python tools/run.py workflows.filtered_noise_validation --output outputs/new-filtered-noise
python tools/verify_filtered_noise_installed.py --output outputs/new-filtered-api
```

## 5. 制約・未解決事項

時刻間で独立・平均0・proper Gaussianのraw電圧、既知で一定の局共分散、固定の有限線形係数とstride、一つの出力channelという仮定です。入力が白いという仮定と、filter後の時刻間の相関を区別しています。

色付き入力、時間変化するsample rate・幾何/rate補正、ADC量子化、RFI/mask、gain変動、channel間相関、実機の信頼区間やCas A画像品質は未検証です。モデル換算数を相関ファイルのFFT数や段階046の独立標本数へ自動代入しません。現行相関/RMLの重み・採否は変更していません。

## 6. 次段階

この検証の日本語GUIを追加し、共通係数の理論換算、局別係数、Monte Carlo差、全共分散の構造差を区別して表示します。その後、実観測に使える保存統計の診断へ接続する方法を検討します。
