# 段階047：相関ファイルの雑音診断

- 作成日：2026-10-03
- 状態：完了（公称FFT数による条件付き診断の範囲）
- 比較元コミット：09db0aa

## 読者向け概要

複数局が共有する天体の信号も揺らぐため、visibility（局間の複素相関）の雑音は基線ごとに独立とは限りません。局power・複素相関・同じ標本を使った回数から、真の天体画像を与えずに雑音の共分散を条件付きで計算する入口を作りました。共分散は、誤差の大きさと誤差同士の関係を表す行列です。

## 1. 目的・対象範囲

整列済み相関NPZへ基線FFT数を追加し、一つの時間・周波数cellをCLIで診断します。FFT数を独立標本数と仮定した診断です。必要情報が不足した場合に推定を返さず、既存相関値・重み・画像復元の意味を維持します。

## 2. 完了条件

同一のFFT集合・単位・完全基線・有効局の条件を確認し、不足やmask差を未判定として返すこと。Gaussian IQ→FFTの標本共分散と一致すること。固定VDIFの再相関で既存V/W/UVW等が変わらないこと。source/wheel全回帰・installed CLI・レポート・匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/aligned.py`：既に内部で計算していた基線ごとの`valid_fft_count`をNPZに保存。FFT長・sample rate・実独立性が未検証というmetadataを追加。相関の計算式は変更していない。
- `apps/correlator/src/vsora_correlator/noise_diagnostics.py`：局powerを対角、visibilityを非対角として標本共分散行列を復元。段階046の有限標本補正、段階044のClosure一次伝播を呼ぶ。2〜8局・完全基線・共通FFT集合・一致する単位・品質flagを確認。
- `pyproject.toml`：`vsora-noise-diagnose` CLIを追加。閉じた入力NPZのSHA256と前後statを確認し、新規JSONだけを作る。
- `apps/correlator/tests/test_noise_diagnostics.py`：Gaussian IQの実FFT統計、共通/異なるmask、情報不足・単位差・flag・不正入力・上書き拒否・模擬VDIFの保存を確認。
- `tools/verify_noise_diagnostic_installed.py`：checkout外で最終wheelを読み、CLIを実行。固定VDIFの再相関と段階037の既存配列を照合。
- [インターフェース](../../interfaces/observation-noise-diagnostic.md)、[学部生向け説明](../guide/07-closure-rml.md)、小容量の検証記録を追加。

`inactive`は有効基線なし、`unverified`はこの推定の必要条件を満たせない状態、`conditional_estimate`は保存情報が揃った条件付き計算です。最後の状態でも独立Gaussianモデルや実機の信頼区間を確認したという意味にはしません。無効Closure行のゼロ値は誤差ゼロの測定として使えません。

## 4. 検証条件・結果

### IQ→FFTの直接計算

seed47・4局・2成分と受信機雑音のproper Gaussian IQ、FFT64、sample rate2.048MHz、512FFTを使用。FXAccumulatorへ8192sample単位で渡し、FFT後の局標本から直接計算した行列と診断結果を照合しました。全局共通の1FFTを除外した511FFTの場合も一致。1局だけ除外した場合は共通集合を確認できないため未判定でした。UVWはダミーで、天体画像の精度試験ではありません。

初回の対象試験は28件成功・1件失敗でした。部分基線を作る試験fixtureが周波数軸を誤って切っており、正しい基線軸へ修正しました。製品の判定条件は緩めていません。修正後・最終ラベル変更後の対象30件は成功、警告640件、2.42秒です。

### 固定模擬VDIFの配布版再相関

段階037の強い線形rate変動の固定入力を使い、既存の最終manifest・clock・測定rate profileで3秒の相関を再実行しました。FFT32・共通192000FFT、中央channel16。生成条件の真値を雑音診断へ渡していません。

visibility・weights・UVW・pairs・時刻・周波数・積分時間の7配列と、既存局診断の5配列、**計12配列がnp.array_equalで完全一致**し、最大配列差は0でした。旧相関ファイルには基線FFT数がないため、推測せず`unverified`を返すことも確認しました。新ファイルのCLIは`conditional_estimate`を返し、SHA256・上書き拒否・実独立性未検証の表示を確認。

別のcheckout外installed CLIでは、実Gaussian IQ→FFT512から作ったNPZを診断しました。両方とも統計の保存・受け渡し・入口の検証です。FIR/ADC後の推定共分散の精度やCas A画像の品質を確認した試験ではありません。

### 全回帰・配布・再現

source全回帰355件成功、警告23312件、610.20秒。全回帰collection後に、visibility共分散の条件付きensemble不偏性と、Closure一次近似に不偏性保証がないことを出力ラベルで分けました。最終ラベルは対象30件と最終wheelで再確認しています。

最終wheelのinstalled全回帰355件成功、警告23312件、633.63秒。sourceの全回帰・最終対象試験、installed CLI・固定VDIF再相関を終えてからinstalled全回帰を実行しました。除外した試験はありません。pip check成功。Python3.12.3・NumPy2.5.1・Baseband4.3.0など既存検証環境を使用。警告は既存のBaseband/NumPy・Starlette等のdeprecationを含みます。

wheel5464360bytes、SHA256 `f8483d04f2cefcdd947f37987bc2d6d77545b719082fc5bcd288daaa326118b2`。最終ラベルを含む`outputs/stage047-wheel-final/`を使用し、途中のwheelは使用していません。

[Gaussian FFTのinstalled CLI](../../validation/runs/stage047/installed-cli.json)、[固定VDIFの比較](../../validation/runs/stage047/vdif-recorrelation.json)、[一cellの診断値](../../validation/runs/stage047/vdif-noise.json)、[全回帰・識別情報](../../validation/runs/stage047/verification.json)を保存。大容量のNPZ・wheel・完全ログはGit外`outputs/stage047-*/`です。入力SHA256は小容量結果に保存しました。

```bash
python tools/run.py vsora_correlator.noise_diagnostics --input correlation/shard-00000.npz --time-index 0 --channel-index 16 --output outputs/new-noise.json
python tools/verify_noise_diagnostic_installed.py --output outputs/new-installed-noise
```

channel16はFFT32の例です。実際の入力の周波数配列を確認して選びます。

ブラウザ用localhost:8765サーバーは、queued/runningジョブがないことを確認して最終wheelで再起動しました。environment API応答と既存39件のジョブ履歴を確認。段階047の新しい診断はCLIのみで、日本語GUIへの追加は次段階です。

## 5. 制約・未解決事項

独立・平均0・proper Gaussian電圧・一定の局共分散を仮定します。FFT block数と実際の独立標本数は区別します。FIR・補間・量子化・RFI・gain変動・有効標本数・実機信頼区間・Cas A復元品質は未検証です。

visibility共分散のensemble不偏性は仮定の下で多数の試行を平均した性質です。一回の推定精度や、測定visibilityを使ったClosure共分散の不偏性を保証しません。現在のrate/RMLの重み・採否を変更していません。

一cellのCLIが対象です。旧ファイル、局統計のないファイル、基線FFT数を保持していない合成ファイルは未判定。部分基線から自動的に小さい局集合を選ぶ機能はありません。ファイルstat確認は通常の変更の検出で、全ての変更を排除する保証ではありません。

## 6. 次段階

この診断の日本語GUI、filter後のFFT間相関と有効独立標本数の検証を検討します。確認できるまで全共分散を実運用RMLへ自動適用しません。
