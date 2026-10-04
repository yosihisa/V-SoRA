# 段階065：三次統計の保存を指定する日本語GUI

- 作成日：2026-10-04
- 状態：完了（合成VDIF・日本語GUIの保存経路の範囲）
- 比較元コミット：4e906fa

## 読者向け概要

観測者が一回の短積分解析と区間列解析の画面から、後で三基線の積を再計算する追加統計を保存できるようにします。保存したことと、統計の不確かさや画像品質を保証したことを区別して表示します。

## 1. 目的・対象範囲

短積分・区間列パイプラインの明示的な保存指定、事前容量検査、厳密なboolのGUI要求、既定で無効の日本語checkbox、共通FFT数・利用可否・容量・元相関照合の表示、実ファイル取得を実装します。現在の画像目的関数は維持します。

## 2. 完了条件

型・事前拒否、実analysis GUIの科学処理とダウンロード、収集有無で相関配列・metadata・相対画像が完全一致。実Chromiumで区間列解析と追加保存の全数値、ダウンロードしたrawと元相関の照合、失敗・中止、日本語font・390px・JS/外部通信を確認。source/wheel全回帰、目視、公開監査、匿名コミット。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/closure_pipeline.py`、`sequence.py`：save_bispectrumのbool、事前容量検査、補正後の最終相関への指定。pilotは既存の平均相関を使います。
- `apps/ui/src/vsora_ui/models.py`：analysis/sequence要求の厳密なbool、既定False。
- `apps/ui/src/vsora_ui/worker.py`：保存範囲の日本語エラー説明。要求の保存指定は既存のoptions経路で渡します。
- `apps/ui/src/vsora_ui/static/index.html`、`app.js`：二つのフォームの日本語checkboxと説明、区間別の共通数・利用可否・容量・元相関照合。
- `apps/ui/tests/test_bispectrum_storage.py`：19件の型、事前拒否、実analysis worker、ダウンロード、既存画像との完全一致。GUI依存がない環境では既存GUI試験と同じ依存検査を使います。
- `tools/verify_sequence_ui.py`：任意の保存指定、実sequenceとanalysisの全表示値、取得したraw/元相関の照合、390px・失敗・中止。
- [GUIガイド](../guide/06-gui.md)、[Closureガイド](../guide/07-closure-rml.md)、索引、小容量の記録。

## 4. 検証条件・結果

対象19件成功、17.82秒、1081件の既存依存の警告。整数・文字列・nullを保存boolとして受理せず、対応外FFTはpipelineの出力を作る前に拒否しました。実analysis GUI workerで補正後相関と追加統計を取得し、保存なしと13相関配列・metadata・相対モデル画像を完全一致で維持しました。元相関とrawの照合、取得bytesの一致、pilotには追加保存しないことを確認しました。

最終対象19件も成功、22.92秒、1081警告。source全723件成功、527.85秒、25596警告。最終wheel5496618bytes、SHA256 `c799206793961805d6dc4a6d42523051e1106795cc1f902c0763d15c5f956110`。pip checkは依存関係の破損なし。最終HTMLは既存のcheck-labelを使います。GUI依存のない環境向けの検査を追加しましたが、今回の環境では全試験を実行しており、除外・skipはありません。

初回ブラウザは、追加した三次統計表も含む一般的な行数selectorで停止しました。rate表の同じ4行を対象にしたselectorに修正し、追加表の全数値と取得したファイルを別途確認しました。科学的な判定閾値は変更していません。

最終の実Chromium153.0.8010.12で、4局・FFT32・0.3秒×3区間、固定gain・区間別既知rateを生成条件に持つ合成VDIFを解析しました。生成seed32、800frame、rate変更は0.514／1.026秒です。10/10工程、0.9秒の名目露光、画像総量1、ADC^2。3区間の共通FFT数は各三角形19200、利用可52/128。追加bytesは15070／15011／15045で、全表示値を照合し、3組のrawと元相関を取得して照合しました。

単一解析でも実画面から保存を選択し、seed23・270frameの別の合成VDIFで5/5工程、共通数19200、利用可52/128、15059bytesの表示と取得ファイルの照合を確認しました。短い入力の区間列は1/2区間で失敗し、実行中の科学subprocessの中止も確認しました。日本語font、390pxのフォームと区間列・単一結果の横あふれなし、JS error0、外部通信0。図を目視確認しました。RMLは100反復の上限に達しており、画像品質や収束の合格判定ではありません。

メインGUIは更新前に稼働中ジョブ0を確認し、最終wheelへ更新して8765番で再起動、応答を確認しました。source、導入版ブラウザ、導入版全回帰の順です。導入版全723件成功、561.26秒、25596警告。除外・skipなし。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、pytest8.4.2、Playwright1.63.0、BLAS/OMP1 thread。公開前に個人情報・秘密情報を監査し、匿名author/committerでコミットします。

記録：[実ブラウザと追加統計](../../validation/runs/stage065/browser.json)、[固定入力の所在・SHA・生成条件](../../validation/runs/stage065/input-provenance.json)、[検証実行](../../validation/runs/stage065/verification.json)、[区間列結果](../../validation/runs/stage065/sequence-result.png)、[390pxの区間列](../../validation/runs/stage065/sequence-mobile.png)、[単一結果](../../validation/runs/stage065/analysis-storage.png)、[390pxの単一結果](../../validation/runs/stage065/analysis-storage-mobile.png)、[保存指定](../../validation/runs/stage065/sequence-input.png)、[失敗](../../validation/runs/stage065/sequence-failed.png)。全ログ・VDIF・取得ファイルはGit管理外のoutputsに保持しました。公開JSONは個人パスを含む全summaryから一般化した項目だけを抽出しています。

## 5. 制約・未解決事項

実FFT・品質選別の独立性、非Gaussian U₃尤度、非常に弱い天体の検出確率、実機位相安定性、Cas A画像品質は未確認です。追加統計は従来のClosure＋RMLに自動適用しません。ブラウザ検証はWSL headless Chromiumで、WindowsブラウザやWSLg画面の直接確認ではありません。

## 6. 次段階

保存した追加統計を指定した時刻・RFで確認し、未計算・利用不可と数値を区別したCLIと日本語GUIを用意します。CLIの試作と合成スペクトルの小試験はGit管理外の `outputs/stage066-preparation/` に残しました。現行の配布ソフトには導入しておらず、正式な段階066は未実施です。低SNRでの画像化には実FFT雑音と尤度の検証が必要です。

5時間枠の残量8%を確認したため、ユーザーの10%未満の終了条件に従い、この段階の検証・レポート・コミットを仕上げて終了します。確認時の週間残量41%。実行中の枠更新はありませんでした。
