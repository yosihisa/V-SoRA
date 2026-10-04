# 段階064：VDIF相関から再解析用の三次統計を保存

- 作成日：2026-10-04
- 状態：完了（合成VDIFの相関・保存経路の範囲）
- 比較元コミット：e2cd40c

## 読者向け概要

収録ファイルVDIFを読み、時計のずれと天体の方向による遅延を補正した後のFFTから、三局共通の追加統計を保存します。二局ごとの平均visibilityだけでは作れないU₃を、後から再計算できるようにします。

## 1. 目的・対象範囲

correlate_alignedとCLIの明示的な保存指定、容量・局数の事前検査、元相関と対応するraw-bispectrum.npz、RF・仰角・品質flagを反映した利用可否、保存失敗時の未完了状態を実装します。今回は相関CLIまでです。GUI・区間列パイプラインは次段階です。

## 2. 完了条件

固定した合成VDIFを収集あり・なしで処理し、元相関の全配列とmetadataが一致。補正後IQを別途FFTして共通集合のU₃と比較。局別無効フレーム、RF除外、仰角不足、ADC/Jyの宣言単位、容量と型の拒否、保存失敗を確認。source/wheel全回帰、checkout外の導入済みCLI、図とmetadataの目視、監査、匿名コミット。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/aligned.py`：明示的な追加収集、事前容量検査、RF guard・仰角を含む利用可否、元相関と照合した独立ファイルの保存。処理notesにclock/rateの識別情報。
- `apps/correlator/src/vsora_correlator/__main__.py`：correlate-alignedの `--save-bispectrum`。
- `tests/integration/test_vdif_bispectrum.py`：16件。実際に処理したIQを捕捉して別途FFT・バッチU₃と比較し、元相関の13配列とmetadataの完全一致を確認。
- `workflows/vdif_bispectrum_validation.py`：固定VDIF、無効フレーム、既知rate、追加保存の対照実験。図に周波数目盛と利用可三角形数のcolorbar。
- `tools/verify_vdif_bispectrum_installed.py`：checkout外の導入済みCLIで同じVDIFを再処理。
- [保存規約](../../interfaces/raw-bispectrum-profile.md)、索引、小容量の記録と図。

## 4. 検証条件・結果

対象16件成功、3.61秒、564件のBaseband/NumPy警告。補正後のIQを捕捉し、独立した全標本FFTとバッチU₃を計算、rtol=10⁻¹⁰・atol=10⁻⁶で一致しました。ADC/Jyはmanifestの宣言単位の保存試験で、実際の絶対flux校正は行っていません。仰角不足では全三角形が利用不可になり、追加保存の例外では完成ディレクトリを作らず.partialに未完了状態を残しました。

seed64、4局、1.42GHz、2.048MHz、FFT長32、0.05秒×2cellの検証用積分です。実機の推奨積分時間を決める試験ではありません。0.14秒・70frameの連続した帯域制限Gaussian点源を生成し、固定gain、既知局rate[0,17.3,-11.7,26.1]Hz、名目通りの既知標本時計を与えました。局0のframe7、局1のframe19を無効化し、FIR65・補間65・幾何・RF位相補正を通しました。rateを自動推定した試験ではありません。

収集あり・なしで元の13数値配列とmetadataが完全一致。三局共通数は[2935,2935,3068,3067]／[3200,3200,3200,3200]。RF/品質/仰角を反映した利用可channel×三角形は96/256。追加ファイル28599bytes、元相関23830bytes。各局の最大buffer12288〜12291標本、最大FX chunk8192標本です。初回workflow全体3.18秒、最大RSS286528KiB、BLAS/OMP1 thread。RSSには合成入力生成と比較対象も含み、相関器だけの常用メモリではありません。

図の目盛とcolorbarを整理し、最終対象16件も成功（3.36秒、564警告）。同一生成条件でworkflowを再実行し、入力SHA・全ての科学的数値が初回と完全一致することを確認しました。最終workflow2.97秒、最大RSS286808KiB。最終図と埋め込まれたmetadataを目視確認しました。

source全704件成功、439.73秒、24516警告。導入済みCLIをcheckout外かつPYTHONPATHなしで実行し、同じVDIFの13配列・metadataの完全一致、追加統計と元相関の照合、既存出力の上書き拒否を確認しました。導入版全704件成功、439.48秒、24516警告。試験除外なし、source、導入済みCLI、導入版全回帰の順です。pip checkは依存関係の破損なし。wheel5495696bytes、SHA256 `0683f2a7d5db3ac7d8ce83f487e8a5c210e617df444766d5de3f4d3b2d63d98d`。

記録：[条件と入力識別情報](../../validation/runs/stage064/vdif-results.json)、[導入済みCLI](../../validation/runs/stage064/installed-api.json)、[検証実行](../../validation/runs/stage064/verification.json)、[図](../../validation/runs/stage064/vdif-bispectrum.png)、[元相関](../../validation/runs/stage064/spectral-visibility.npz)、[追加統計](../../validation/runs/stage064/raw-bispectrum.npz)。大容量VDIFと全ログはGit管理外のoutputsに置き、公開記録に4ファイルのSHA・bytes・生成条件を残しました。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、pytest8.4.2、既存Astropy7.2.2/Baseband4.3.0。公開前に個人情報・秘密情報を監査し、匿名author/committerでコミットします。

## 5. 制約・未解決事項

FIR・補間後の実FFTと品質選別の独立性、三次統計の実機尤度、弱い天体の検出確率、未知rateの回復と画像品質は今回の合格条件に含めません。ここでは入力と既知rateを与えたデータ経路を確認します。RMLの尤度と重みは変更しません。

## 6. 次段階

短積分と区間列のパイプラインからも任意に保存し、日本語GUIに保存指定と容量・共通数・利用可否を表示します。
