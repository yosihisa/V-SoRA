# 段階055：時間相関が三基線積へ与える偏り

- 作成日：2026-10-04
- 状態：完了（既知ゼロ源モデルの検証の範囲）
- 比較元コミット：a643c15

## 読者向け概要

フィルターで近くの標本が同じ入力を使うと、その雑音には時間相関が生じます。異なる標本番号を選ぶだけでは独立にはなりません。天体信号がない既知モデルで三基線の積の平均を調べ、入力を共有しない間隔で間引く場合と比較しました。

## 1. 目的・対象範囲

独立な3受信局、天体相互相関ゼロ、既知proper Gaussian時間共分散に限り、通常の三基線積と異標本U₃の期待値を計算します。有限フィルターの白色入力モデルを比較します。

## 2. 完了条件

小標本で全添字を列挙して期待値と照合。直接白色作用素と共分散を照合。5条件×8192試行で実虚平均を事前の6 MC SE基準と比較。間引き後のモデル共分散と保持数を確認。source/wheel全回帰・checkout外API・図の目視・公開情報確認・レポート・匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/simulator/src/vsora_simulator/bispectrum_temporal.py`：有限係数の時間共分散、3局の既知時間共分散から通常積/U₃の期待値を計算する実験API。M3〜256、有限/Hermitian/半正定値の数値確認、masked拒否、入力保持。
- `apps/simulator/tests/test_bispectrum_temporal.py`：27件の全添字列挙・直接作用素・白色/間引き・固定gain・異なる局の非定常共分散・拒否・workflow。
- `workflows/bispectrum_temporal_validation.py`：白色、65標本平均、基準FFT32中央ch、各間引きの5条件×8192反復、既知平均・MC平均/SE/共分散・保持数・図。
- `tools/verify_temporal_bispectrum_installed.py`：checkout外のinstalled APIを独立列挙と照合。
- [API・式・結果](../../interfaces/temporal-bispectrum.md)、[Closureガイド](../guide/07-closure-rml.md)、索引、小容量記録。

期待値の式は局独立性と標本添字の包除からローカルに導出しました。`K₀[a,c] K₁[b,a] K₂[c,b]`の全和と、添字が一致する面/線の和を行列積で計算します。天体真値0でも時間相関があればU₃の平均が非零になり得ます。基線の向きはi→j→k→iです。

## 4. 検証条件・結果

対象27件成功、0.73秒。M3/4/7で全添字と順序付き異添字を独立列挙。基準FIR・補間・FFT32係数のδ0/0.25/0.75で直接作用素AのA Aᴴと一致。白色・固定gain power・任意の局別非定常PSD共分散で複素平均が残る例も確認しました。非定常の例を、全ての定常FIRが複素偏りを持つという主張には使いません。

白色K=Iの通常積平均は1/128²、U₃平均は0。長い平均の通常積理論平均0.0021753046、U₃理論平均0.0013449723に対し、U₃反復平均0.0013052110−0.0000035362i、実虚MC SE約0.0000777844/0.0000699994でした。残留偏りはこの固定モデルの試行数で分解できます。基準FFTモデルのU₃平均は約4.97e−15で、今回のMC SE約5.6e−6では分解できません。極小の理論値は差の浮動小数点誤差も受け、実機の誤差上限にはしません。

平均の出力を9個おき、基準FFTを5個おきにすると、白色固定係数モデルの共分散は単位行列となり、U₃理論平均は0。保持数は128→15/26、U₃の実虚MC SEも約1.4e−4/6.1e−5へ大きくなりました。通常積の白色バイアスは1/M²となり、保持数を減らすと増えます。5条件の両方法・実虚平均は全て事前の6 MC SE+1e−12基準に整合。試行後のseed選び直しはしていません。

Gaussian係数は既知時間共分散KのCholesky分解から生成。物理的raw畳み込み・ADC・VDIFを行った実験とは区別します。直接作用素との対応は別の対象試験で確認しました。反復計算1.14秒、最大RSS142528KiB、BLAS/OMP1 thread。図は目視確認済みです。

source511件成功、警告23952件、430.49秒。installed511件成功、警告23952件、424.35秒。試験除外なし、source→installed全回帰の順、既存deprecation警告を含み、pip check成功。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Pytest8.4.2、Matplotlib3.11.1、WSL Ubuntu。checkout外APIの全列挙との最大差約5.00e−17、長い平均と15保持の間引き結果も一致しました。

wheel5481649bytes、SHA256 `e3422531e222091111f8e58e42c9417fb3f1f4138294718921afb124cfee17c4`。

[反復計算](../../validation/runs/stage055/gaussian.json)、[図](../../validation/runs/stage055/bispectrum-temporal.png)、[installed API](../../validation/runs/stage055/installed-api.json)、[回帰・wheel](../../validation/runs/stage055/verification.json)。完全ログ・wheelはGit外`outputs/stage055-*/`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.bispectrum_temporal_validation --output outputs/new-temporal-bispectrum
python tools/verify_temporal_bispectrum_installed.py --output outputs/new-temporal-installed
```

初回の文書配置を修正し、リンク検査で検出した既存文書名の誤りも修正しました。科学計算の失敗はありません。

## 5. 制約・未解決事項

既知ゼロ源モデルです。局間独立・proper Gaussian・固定係数・固定gainを仮定し、未知観測共分散を推定しません。色付き入力、局間雑音、時間変化gain、時計変動では、入力範囲が離れても独立性を保証できません。MC SEは既知モデルの有限試行誤差で、実機の信頼区間や検出確率ではありません。間引きの実機推奨・感度保証・画像品質・角度の不偏性は未検証。現行相関器とRMLの統計・重み・採否は変更していません。

## 6. 次段階

今回のモデルと保持数の損失を日本語の検証GUIへ接続し、観測者が条件を読み取れる表示を検証します。
