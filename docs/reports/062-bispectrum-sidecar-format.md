# 段階062：三次統計の保存形式と元相関ファイルの照合

- 作成日：2026-10-04
- 状態：完了（保存形式と合成データの範囲）
- 比較元コミット：956ab56

## 読者向け概要

三次統計の追加の和を独立したファイルへ保存し、後でU₃を再計算できるようにします。元のvisibilityファイルの識別情報と時刻・周波数・局ID・単位を照合し、観測の取り違えを検出します。

## 1. 目的・対象範囲

version1のraw bispectrum NPZ形式、厳密な入力検査、上書きしない原子的な保存、再読込・U₃再計算、元のspectral NPZとの任意の照合を実装します。相関器のVDIF経路とRMLへの自動適用は次段階以降です。

## 2. 完了条件

ADC/Jy単位、数値配列の完全読戻し、バッチU₃と一致。時刻・周波数・局・単位・FFT設定・SHA・保持数・同じ集合の辺平均・利用不可基線との不整合を拒否。容量、NPZ version/header/object/余分な項目、不正配列とmetadata、保存失敗・競合時の上書き防止。合成IQの二cellと局別欠損、source/wheel全回帰、checkout外API、図の目視、公開情報監査、レポートと匿名コミット。

## 3. 実際に行った作業

- `packages/formats/src/vsora_formats/bispectrum.py`：version1の保存・読込・U₃再計算。shape・値・単位・ID・保持数・未確認flag・header・容量を検査。新規出力だけを原子的に作成。
- `packages/formats/tests/test_bispectrum.py`：59件の完全読戻し、単位、拒否、元ファイル照合、保存失敗と競合時の清掃、二cellのworkflow。
- `workflows/bispectrum_sidecar_validation.py`：局別欠損のある合成IQをchunk FFTし、元visibilityと追加統計を保存・再計算・照合。
- `tools/verify_bispectrum_sidecar_installed.py`：checkout外の導入版で再計算と元ファイルの照合。
- [形式の規約](../../interfaces/raw-bispectrum-profile.md)、[Closureガイド](../guide/07-closure-rml.md)、索引、小容量記録。

## 4. 検証条件・結果

対象59件成功、0.50秒。raw配列の完全読戻し、バッチU₃一致、ゼロ保持数の利用不可、ADC/Jyの宣言単位を確認。不正配列・metadata・mask・J・version・object・余分な項目・宣言payloadとの容量矛盾を拒否。40MiB上限の定数と、閾値を小さくした試験で拒否分岐を確認しました。実40MiBファイルの処理性能は未測定です。原子的保存の失敗と、保存中に出力先が出現する競合でも既存ファイルを上書きせず、一時ファイルを清掃しました。

元ファイルのSHA256、時刻軸・周波数軸・局ID・UTC原点・単位・FFT長・標本周波数の不一致、FFT数不足・共通数の過大宣言、同じ集合の辺平均の不一致、無効辺を利用可にする不整合を拒否しました。

seed62、4局・2cell・8channel・各17block、標本周波数1024Hzを設定した合成Gaussian IQです。4blockずつFFT・蓄積を実行しました。この標本周波数は保存形式用の設定で、RTL-SDRへの推奨ではありません。cell0は局0の先頭2blockと局1の7〜8番の2block、cell1は局2の末尾3blockと局3の先頭1blockを決め打ちで無効化しました。三角形の共通数は[13,13,15,15]／[14,16,13,13]で、元ファイルの二局ごとの数と異なるケースを確認しました。

raw配列の読み戻しは完全一致。再計算したU₃とバッチの最大絶対差3.273070×10⁻¹⁷。元visibilityは3999bytes、raw sidecarは10066bytes。全体0.36秒、最大RSS79868KiB、BLAS/OMP1 thread。図を目視確認しました。UVW0と任意の正重みは形式検証用で、観測幾何や雑音モデルの値ではありません。物理的ADC・VDIF・FIR・時計・LO・幾何補正は処理していません。

入力IQ complex128 little endianのSHA256 `84b9ee61fd6a69a51891a1e2b3d26bdb4ee79a688a31c8a7a8c1ff878ba23048`、元visibilityのSHA256 `bd6263715346cb18e9005ef9d100a22d724a5f968de97b3b3cd272162e0044b5`。

source全体669件成功、428.83秒。wheel導入後の全体669件成功、432.50秒。いずれも23952件の既存依存ライブラリ等の警告を含み、除外した試験はありません。source、導入版API、導入版全回帰の順に実施しました。checkout外かつPYTHONPATHなしの導入版APIで、raw U₃の再計算、元相関の識別、同じFFT集合の辺平均を確認しました。pip checkは依存関係の破損なし。wheelは5494183bytes、SHA256 `012605ebb3662e57e7c963cfff9afec79721713fba4838d5395c2b9791dbb1a2`。

記録：[条件・数値](../../validation/runs/stage062/sidecar-results.json)、[検証実行](../../validation/runs/stage062/verification.json)、[導入版API](../../validation/runs/stage062/installed-api.json)、[図](../../validation/runs/stage062/bispectrum-sidecar.png)、[元相関](../../validation/runs/stage062/spectral-visibility.npz)、[追加統計](../../validation/runs/stage062/raw-bispectrum.npz)。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、pytest8.4.2、BLAS/OMP1 thread。公開前の個人情報・秘密情報監査を実施します。

## 5. 制約・未解決事項

ファイルの識別・配列の整合性は、実FFTの独立性、未知gainや時計の安定、非Gaussian尤度、実機と画像品質を保証しません。異なる有効集合のraw sumsは平均visibilityだけでは照合できません。合成検証のUVW0と任意の正重みは保存形式用で、観測幾何・雑音モデルの検証に使いません。

## 6. 次段階

実際のFX処理で明示的に追加統計を蓄積し、VDIFから元相関とraw bispectrumの対応を保存できるよう接続します。
