# 段階066：保存した三次統計を時刻と周波数で確認

- 作成日：2026-10-05
- 状態：完了（保存値・元相関の識別と必要な整合性の範囲）
- 比較元コミット：`d0d4fe3`

## 読者向け概要

保存した追加統計からU₃を再計算し、指定した時刻と周波数で値と有効標本数を確認します。FFT数不足の「未計算」、品質flagによる「利用不可」、形式上利用できるraw値を区別します。雑音のσや画像の信頼性を与える機能ではありません。

## 1. 目的・対象範囲

一cellのraw値と三角形別状態のAPI/CLI、元相関の必須照合、読込中の変更検出、上書き防止、有限JSONを実装します。通常の積は三局共通集合の辺平均の積です。GUIでの時刻・RF選択は次段階です。

## 2. 完了条件

元配列を変えず実部・虚部・数を再計算結果と一致させる。M0/1/2をnullと区別し、品質mask、局別欠損、添字・不完全入力、原本変更・不整合、既存出力を検査。保存済みVDIF相関の利用可/不可cellを確認。source/wheel全回帰、checkout外CLI、公開監査、匿名コミット。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/bispectrum_inspect.py`：指定cellのAPIと、元相関を必須とするファイルAPI。実部・虚部、三局共通FFT数、三つの状態を有限JSONで返します。
- `pyproject.toml`：配布CLI `vsora-bispectrum-inspect`。
- `apps/correlator/tests/test_bispectrum_inspect.py`：欠損・マスク・M0/1/2・添字・読込中の変更・原本不整合・上書き・入力不変性の20件。
- `tools/verify_bispectrum_inspect_installed.py`：checkout外で導入済みCLIを動かし、固定JSONとの完全一致と上書き拒否を確認する手順。
- [入力・出力規約](../../interfaces/bispectrum-inspection.md)、[利用ガイド](../guide/07-closure-rml.md)、[小容量の検証記録](../../validation/runs/stage066/stored-cell-results.json)。

SHA256はファイル内容の識別情報です。前後のファイル状態も比較し、読込中に変更された原本では新しい結果を作りません。三角形の標本不足はnull、品質マスクではraw値を残します。元相関との一致は、保存形式の識別と必要な整合性の確認です。処理全体の正しさや独立性を証明するものではありません。

## 4. 検証条件・結果

### 個別検証

Python3.12.3、NumPy2.5.1、SciPy1.18.0、Pytest8.4.2、BLAS/OMP各1threadで、個別20件は成功しました。M0/1/2のU₃が数値ゼロではなくnull、品質マスクと欠損時の値が再計算結果と一致、配列は不変であることを確認しました。

### 保存済みVDIF相関の確認

段階064の合成Gaussian電圧をcomplex8-bit VDIFへ記録し、FIR65・補間65・幾何補正を経た保存済みファイルを再利用しました。実機の収録ではありません。入力のSHAは[識別記録](../../validation/runs/stage066/stored-cell-results.json)に保存しています。時刻はUTC原点から0.027秒、候補FFT数3200です。

| RF | 三局共通FFT数 | 四つの三角形の状態 | 元相関照合 |
| --- | --- | --- | --- |
| 1419.616 MHz（channel10） | 2935、2935、3068、3067 | 形式上利用可 | 一致 |
| 1420.000 MHz（channel16） | 同上 | RFマスクで利用不可 | 一致 |

全桁の複素数は[利用可cell](../../validation/runs/stage066/active-cell.json)と[マスクcell](../../validation/runs/stage066/masked-cell.json)を参照してください。これは保存値の確認であり、測定誤差を推定した結果ではありません。

実行例：

```bash
python tools/run.py pytest -q apps/correlator/tests/test_bispectrum_inspect.py
python tools/run.py vsora_correlator.bispectrum_inspect --input validation/runs/stage064/raw-bispectrum.npz --source-visibility validation/runs/stage064/spectral-visibility.npz --output outputs/new-inspection.json --time-index 0 --channel-index 10
```

### 全回帰・配布物・公開監査

source743件成功、警告25596件、468.18秒。installed743件成功、警告25596件、465.12秒。試験除外なし。source全回帰→導入→checkout外CLI→installed全回帰の順で実施しました。既存のdeprecation警告を含みます。pip checkは成功です。

導入済みCLIはcheckout外・PYTHONPATH除去で実行し、固定の利用可cellのJSONと全項目が一致しました。既存出力を上書きしないことも確認しました。[CLI記録](../../validation/runs/stage066/installed-cli.json)。

wheel5498947bytes、SHA256 `8d4c4a2eedc45829568242e640b7578ab697e274b2a866988b69501fe32bf3f2`。配布物の全パッケージファイルとsourceの一致を確認しました。件数等は[回帰・wheel記録](../../validation/runs/stage066/verification.json)を参照してください。完全ログとwheelはGit外 `outputs/stage066-*/` に保存しました。

文書リンク600個に不足0、公開前監査0件、差分の空白検査成功。追加の公開JSONは数値・一般化した入力名・SHAだけで、個人情報やローカルユーザーパスを含みません。author/committerは公開用のV-SoRA contributorsを使います。

## 5. 制約・未解決事項

三局共通FFT数は実独立標本数ではありません。通常の積とU₃の差を実機の偏りの推定値とは扱いません。未知gainの正規化、非Gaussian尤度、雑音共分散と信頼区間、弱信号の検出確率、Cas A画像品質は未検証です。RMLには適用しません。

## 6. 次段階

保存したrawと元相関を日本語GUIで選び、時刻・RFと三角形別の値と状態を確認できるようにします。低SNRへの適用には実FFTの雑音と尤度の検証を続けます。
