# 段階063：相関器のFFTから三次統計を収集

- 作成日：2026-10-04
- 状態：完了（合成IQのFX収集の範囲）
- 比較元コミット：edcd9ae

## 読者向け概要

相関器は二局のFFT値の積を平均してvisibilityを作ります。このFFT値を使って三局共通の追加の和も集め、後で異なる標本の三基線積U₃を計算できるようにします。欠損があると二局共通の標本数と三局共通の標本数は異なります。

## 1. 目的・対象範囲

FXAccumulatorに明示的なcollect_bispectrumオプションを追加し、三局共通の有効FFT、追加統計、周波数順、利用可否を返します。既定の相関値・重み・診断配列を完全一致で維持します。今回は合成IQからのFX処理で、VDIF経路への接続は次段階です。

## 2. 完了条件

オプション有無で既存の全配列が完全一致。局別欠損、品質flag、周波数順、M<3、局数・型・mask・過大値・保持数の拒否を確認。0.1秒の固定gain合成IQで独立したバッチU₃と一致。source/wheel全回帰、checkout外API、図の目視、匿名公開の監査、レポートとコミット。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/stream_fx.py`：collect_bispectrum=Trueの場合だけ、同じFFTと局別有効maskを追加蓄積器に渡します。周波数順を揃え、M≥3と全構成基線の正重みから利用可否を作ります。
- `apps/correlator/tests/test_fx_bispectrum.py`：既存配列の完全一致、バッチとの比較、欠損、品質flag、拒否、既定二局、保持数不足、0.1秒workflowの19件。
- `workflows/fx_bispectrum_validation.py`：固定gainと局別欠損を含む0.1秒合成IQの対照実験。
- `tools/verify_fx_bispectrum_installed.py`：checkout外で導入版の既存配列とバッチを比較。
- [収集APIの規約](../../interfaces/streaming-bispectrum.md)、索引、小容量の数値記録と図。

## 4. 検証条件・結果

対象19件成功、0.47秒。3〜8局・FFT長2〜4096に限定し、bool以外の収集オプション、masked入力と非bool mask、過大値、保持数上限を拒否しました。追加蓄積を拒否したconsumeではFXの数値状態も変化しません。既定の二局FXは継続して利用できます。

seed63、4局・FFT長32・6400block、2.048MHz・1.42GHz、名目0.1秒のGaussian IQです。S=I+0.1×全要素1の共分散を作り、局gain振幅[1,0.8,1.2,2]、位相[0,0.2,-0.7,1.1]radを固定しました。最大chunk256blockです。全有効と、局0の101blockおき・局1の127blockおきの欠損、1channelの既知RF除外とSK/電力診断の二条件を比較しました。

全有効は既存7数値配列、品質ありは12数値配列を完全一致で維持し、説明文字列も一致。三角形共通数は[6400,6400,6400,6400]と[6286,6286,6336,6350]です。独立した全標本バッチU₃との差は最大4.774573×10⁻¹⁷／3.861039×10⁻¹⁷。利用可channel×三角形は128／124でした。

同一実行のFX時間は収集なし0.01235／0.01254秒、あり0.02948／0.02535秒。workflow全体0.49秒、最大RSS120460KiB、BLAS/OMP1 thread。単一測定で機種横断の性能保証ではありません。RSSには検証用の全IQ・全FFT参照も含みます。図を目視確認しました。入力complex128 little endian SHA256 `3a99f823bfd19022558cc6761975e539299df830f90f4b18e2c051297268936b`。

source全688件成功、433.88秒。wheel導入後の全688件成功、432.77秒。いずれも23952警告、試験除外なし。source、checkout外の導入版API、導入版全回帰の順です。導入版APIでも既存配列の完全一致とバッチU₃を確認しました。pip checkは依存関係の破損なし。wheel5494590bytes、SHA256 `cc06845dd483fe452271bb4f758b4668231532cce5f1388aadc29cd0bc6500ff`。

記録：[条件・数値](../../validation/runs/stage063/fx-results.json)、[導入版API](../../validation/runs/stage063/installed-api.json)、[検証実行](../../validation/runs/stage063/verification.json)、[図](../../validation/runs/stage063/fx-bispectrum.png)。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、pytest8.4.2。公開前に個人情報・秘密情報を監査し、匿名author/committerでコミットします。

## 5. 制約・未解決事項

追加の和を保存できても、実FFTの独立性やデータに依存する品質選別の独立性は保証しません。固定gain合成IQの検証で、物理的ADC・VDIF・FIR・時計・LO・幾何補正、実機、画像品質は未検証です。RMLの尤度と重みは変更しません。

## 6. 次段階

VDIFを読み、時計・幾何補正を実行する経路から、元相関に対応する追加統計ファイルを出力します。
