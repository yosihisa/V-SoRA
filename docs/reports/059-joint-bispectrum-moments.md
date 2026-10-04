# 段階059：天体信号を含む三基線積の雑音共分散

- 作成日：2026-10-04
- 状態：完了（既知独立Gaussian電圧モデルの範囲）
- 比較元コミット：9269b56

## 読者向け概要

天体信号があると三基線積の雑音は変わります。共有アンテナを持つ三角形の間の共分散も含め、既知Gaussian電圧モデルで異標本量U₃の平均と散らばりを検証します。

## 1. 目的・対象範囲

既知の局共分散S、標本間独立・proper Gaussian・一定gainに限り、有限MのU₃の複素共分散Γ、擬共分散Π、全実共分散を計算します。三角形内は異なる添字、二つの三角形の標本共有は部分対応として数えます。観測共分散の推定やRML尤度は対象外です。

## 2. 完了条件

小Mの全時間添字とWick縮約を独立列挙。34部分対応の重み、ゼロ源・完全共通信号・固定gain・共役・subset・PSD・入力拒否を確認。5条件×8192試行で平均と全実共分散を事前の6 MC SE基準と比較。source/wheel全回帰、checkout外API、図の目視、公開情報確認、レポートと匿名コミット。

## 3. 実際に行った作業

- `apps/simulator/src/vsora_simulator/bispectrum_moments.py`：既知Sと独立標本数Mから、全三角形の平均、複素共分散Γ、擬共分散Π、全実共分散を計算する実験API。
- `apps/simulator/tests/test_bispectrum_moments.py`：小Mの独立添字列挙、重み、特殊極限、固定複素gain、入力拒否、反復検証、失敗結果の保存を含む31件。
- `workflows/bispectrum_moments_validation.py`：4局・4三角形の5条件×8192試行、平均と8×8実共分散、Monte Carlo標準誤差、図。
- `tools/verify_bispectrum_moments_installed.py`：checkout外のinstalled API、ゼロ源と固定gain変換、PSD、未確認flag。
- [式と入力条件](../../interfaces/joint-bispectrum-moments.md)、[Closureガイド](../guide/07-closure-rml.md)、索引、小容量記録。

二つのU₃の標本共有を34通りの部分対応として数え、平均積を除いた105個のGaussian縮約積を直接加算します。平均積を大きな二次モーメントから数値的に引く方式を避けました。式はローカルに導出し、小Mの全時間添字とGaussianの二次モーメントの縮約による別実装と照合しました。

## 4. 検証条件・結果

対象31件成功、1.16秒。M3/4で二つの異添字三つ組の全組合せを列挙し、各時刻のGaussian縮約からΓ/Πの全成分を照合。M3/4/5/6/128/100万の対応重みの総和、ゼロ源・完全共通信号・固定複素gain・共役・subset・PSD・入力保存・不正入力・数値範囲も確認しました。

5条件は局間独立のゼロ源、弱い共通信号、より強い共通信号、位相の異なる二成分、雑音を加えない完全共通信号です。4局から4三角形を作り、既知Sからproper Gaussian電圧を発生させました。各8192試行で、実虚平均と全64個の実共分散成分が事前の6 MC SE＋丸め許容基準内でした。観測値による試行選別はしていません。

| 既知モデル | M | 天体あり複素分散／同じ局powerのゼロ源分散 | 最大の実成分間の相関絶対値 | MC共分散の最大標準化差 |
|---|---:|---:|---:|---:|
| ゼロ源 | 128 | 1 | 0 | 0.085380 |
| 弱い共通信号 | 128 | 1.000377 | 0.00000127 | 0.046717 |
| 共通信号 | 128 | 7.509520 | 0.250355 | 0.040423 |
| 二成分 | 32 | 6.336097〜16.425592 | 0.487646 | 0.086971 |
| 完全共通信号 | 32 | 8916 | 1 | 0.010957 |

標準化差はモデル共分散の対角標準偏差で割った比較量で、合否の閾値ではありません。合否は各成分の反復計算の標準誤差によります。完全共通信号は全局に同じ電圧を与えた特殊極限で、独立受信機雑音を含みません。実機の分散倍率として採用する数値ではありません。

初回のファイル生成試験だけ試行数を128へ減らしたところ、二成分モデルの共分散で6.140 MC SEとなり、6 MC SE基準を超えました。事前に計画していた科学検証の8192試行は合格しました。ファイル試験も実際の既定8192試行へ合わせ、128試行時の失敗は別試験で確認しました。失敗時にはJSONを`failed_validation`として保存し、図と数値を残して例外を返します。seedや合否基準を選び直していません。

最終反復計算0.88秒、最大RSS85448KiB、BLAS/OMP1 thread。図を目視確認しました。物理的ADC、VDIF、FIR、未知LO補正は処理していません。

source571件成功、警告23952件、424.40秒。installed571件成功、警告23952件、422.02秒。試験除外なし、source→installed API→installed全回帰の順、既存deprecation警告を含み、pip check成功。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、Pytest8.4.2、WSL Ubuntu。checkout外APIで、ゼロ源の正確な式・固定gainの共分散変換・PSD・未確認flagを確認しました。

wheel5487303bytes、SHA256 `32768c89d59fb0fadb81aaa1edda6b934d0c008984337a2d53f54a9166c1fa98`。

[反復結果と全共分散](../../validation/runs/stage059/known-gaussian-moments.json)、[図](../../validation/runs/stage059/bispectrum-moments.png)、[installed API](../../validation/runs/stage059/installed-api.json)、[上限寸法](../../validation/runs/stage059/max-dimensions.json)、[回帰・wheel](../../validation/runs/stage059/verification.json)。完全ログ・wheelはGit外`outputs/stage059-*/`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.bispectrum_moments_validation --output outputs/new-bispectrum-moments
python tools/verify_bispectrum_moments_installed.py --output outputs/new-bispectrum-moments-installed
```

## 5. 制約・未解決事項

実機の共分散、FFT時間相関、量子化、未知rate/gain補正の依存、標本powerによる正規化、非GaussianなU₃尤度、角度の信頼区間、画像復元は未確認です。

既知Sを与えて計算する実験APIです。導入版で既知の乱数PSD入力を使い、8局・56三角形、M3/100万の112×112実共分散の有限性と半正定値を追加確認しました。最小固有値は約1.722688／1.486752×10⁻¹³でした。上限寸法でのMonte Carlo検証は行っておらず、今回の反復比較は4局・4三角形です。Gaussian電圧の正確な平均・共分散は、三次統計の分布全体がGaussianであることを意味しません。

## 6. 次段階

条件と共分散検証結果を日本語GUIへ接続します。
