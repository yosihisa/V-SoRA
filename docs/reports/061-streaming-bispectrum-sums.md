# 段階061：三次統計の追加の和を少ないメモリで蓄積

- 作成日：2026-10-04
- 状態：完了（追加統計の実験APIと状態APIの競合修正）
- 比較元コミット：9384e3a

## 読者向け概要

異標本の三基線積U₃は、平均visibilityだけからは再計算できません。FFT係数を処理しながら必要な追加の和を蓄積する実験機能を作り、データを分割しても一括計算と一致することを確認します。

## 1. 目的・対象範囲

FFT係数の複素配列から、三角形の3局に共通する有効blockだけを使い、辺の和・辺の積の和・三辺の積の和を蓄積。各三角形の共通保持数と利用可否を残します。既存相関器のvisibility、VDIF経路、RMLへの自動適用はこの段階の対象外です。

全回帰で成果物一覧の取得競合も発見したため、ジョブ状態APIの誤404を再現試験で修正します。

## 2. 完了条件

独立した小M全添字列挙、バッチU₃との一致、chunk分割、3/4/8局、maskと三角形ごとの共通集合、M0/1/2/3、固定gain、subset、入力拒否・失敗chunkの原子性・overflow・上限寸法・固定状態容量を確認。合成IQ→chunk FFT→追加統計→保存の照合。source/wheel全回帰、checkout外API、図の目視、公開情報監査、段階レポートと匿名コミット。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/bispectrum_accumulator.py`：FFT係数をchunkで受け取り、各三角形の共通集合の辺の和A、二辺の積の和H、三辺の積の和Jと保持数Mを蓄積する実験API。
- `apps/correlator/tests/test_bispectrum_accumulator.py`：36件の独立添字列挙、バッチ照合、mask・不足標本・gain・拒否・原子性・数値範囲・上限寸法・workflow。
- `workflows/streaming_bispectrum_validation.py`：合成IQ→chunk FFT→追加統計を、原本の一括FFTとバッチU₃へ照合。検証用NPZでraw sumsを保存して読み戻し。
- `tools/verify_bispectrum_accumulator_installed.py`：checkout外の導入版で、局ごとのmaskを含む分割処理とバッチを照合。
- `apps/ui/src/vsora_ui/server.py`、`apps/ui/tests/test_server.py`：成果物一覧で各pathのstatを一回だけ取得し、移動で消失したpathはその一覧から除外。ジョブの状態を誤404にしない競合回帰2件を追加。
- [入力と式](../../interfaces/streaming-bispectrum.md)、[Closureガイド](../guide/07-closure-rml.md)、索引、小容量記録。

## 4. 検証条件・結果

正式なリポジトリ内の対象36件成功、0.39秒。M5の全順序付き異添字の直接積と照合。3/4/8局の全三角形・chunk分割、局ごとの欠損、M0/1/2/3、固定複素gain、subset、入力保存、失敗chunkの原子性、consume/finishのoverflow拒否、二回目finish拒否、8局×4096channelの上限寸法と固定数値状態容量を確認しました。

seed61、4局・32channel・257FFT block、局共分散I＋0.1×全要素1を使う合成Gaussian IQを発生。7blockずつFFTと蓄積を実行し、一括FFTとバッチU₃へ照合しました。局0の先頭3block、局1の20〜23番の4block、局2の末尾5blockを決め打ちで無効化した条件も比較しました。信号値による選別はしません。

| 条件 | 三角形ごとの共通保持数 | 分割U₃とバッチの最大絶対差 | 分割通常積とバッチの最大絶対差 |
|---|---|---:|---:|
| 全block有効 | 257 / 257 / 257 / 257 | 9.543443×10⁻¹⁸ | 8.673617×10⁻¹⁸ |
| 決め打ちの局別欠損 | 245 / 250 / 249 / 248 | 5.485677×10⁻¹⁸ | 6.209365×10⁻¹⁸ |

蓄積器の数値状態は各14368bytes（`112 F K＋8 K`）、最大入力chunkは7block。検証全体0.33秒、最大RSS81472KiB、BLAS/OMP1 thread。比較用の原本IQと一括FFTも保持しており、このRSSを実運用の必要メモリとしません。保存raw arraysの読み戻しは全値完全一致。図を目視確認しました。物理的ADC・VDIF・FIR・LO補正は処理していません。検証用NPZはこの段階の小容量記録であり、公開の観測保存形式の定義は次段階です。

入力IQはcomplex128 little endianのバイト列のSHA256 `c5ffd78f4c105f5c8c82b97f37b92d4514dc342c4fb09e02ac4ce80ac8a6ad28`。

### 全回帰で発見したジョブ状態APIの競合

初回source608件成功、450.36秒。初回installedは607件成功・1件失敗、425.07秒、警告23952件。失敗した`test_sequence_gui_real_subprocess_and_failure`では、状態APIの応答に`state`がなく、試験側でKeyErrorになりました。成果物のディレクトリ移動中、`is_file()`の後の`stat()`でファイル消失が起きると、APIがジョブ全体の404を返す経路がありました。

小さな試験で、最初のstatの後にファイルを消すと従来コードが404を返すことを決定的に再現しました（修正前1件失敗・1件成功、0.22秒）。一回のstatから通常ファイル判定と容量を得る方式にし、stat前に消えたpathも一覧から除きます。修正後の競合2件と従来90秒上限の実区間列GUI試験の計3件成功、34.92秒、警告4281件。最終source/wheel/実ブラウザ/installed全回帰で再確認しました。初回失敗と最終合格を区別して残します。

最終source610件成功、警告23952件、423.44秒。最終installed610件成功、警告23952件、429.22秒。試験除外なし、source→installed API/実ブラウザ→installed全回帰の順、既存deprecation警告を含み、pip check成功。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、Pytest8.4.2、WSL Ubuntu。checkout外の導入版で局ごとのmask、共通保持数、chunk処理とバッチの一致、未確認flagを照合しました。

最終wheel5490218bytes、SHA256 `f9bbb993dde8ef9d8ebd4fa2e82b9723f826116a74c5e53fdd61dd07bcb4866b`。

導入済みGUIを独立workspaceのChromium153.0.8010.12／Playwright1.63.0で操作。固定seed32の800frame VDIF、0.514/1.026秒で局rateが変わる3区間が10/10工程完了、名目露光0.9秒、相対画像総和1、ADC²入力を確認しました。RMLは100反復の上限でoptimizer_success=Falseであり、画像品質の合格ではありません。不足VDIFは2区間中1区間を終えて停止、別の実subprocessを起動して中止も確認。日本語font読込、390px幅のform/resultに横overflowなし、JSエラー0、外部通信0。desktop/mobile/失敗図を目視確認。Windowsブラウザ／WSLgは今回未検証です。通常GUIは実行中ジョブ0を確認して最終導入版へ更新しました。

[蓄積結果](../../validation/runs/stage061/streaming-results.json)、[図](../../validation/runs/stage061/streaming-bispectrum.png)、[全有効raw arrays](../../validation/runs/stage061/all-raw-sums.npz)、[欠損raw arrays](../../validation/runs/stage061/deterministic_gaps-raw-sums.npz)、[installed API](../../validation/runs/stage061/installed-api.json)、[ブラウザの匿名化記録](../../validation/runs/stage061/sequence-browser.json)、[desktop](../../validation/runs/stage061/sequence-result.png)、[mobile](../../validation/runs/stage061/sequence-mobile.png)、[不足入力](../../validation/runs/stage061/sequence-failed.png)、[全回帰・失敗履歴・wheel](../../validation/runs/stage061/verification.json)。完全ログ・wheel・VDIFはGit外`outputs/stage061-*/`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.streaming_bispectrum_validation --output outputs/new-streaming-bispectrum
python tools/verify_bispectrum_accumulator_installed.py --output outputs/new-streaming-bispectrum-installed
```

## 5. 制約・未解決事項

FFT標本の独立性、信号に依存したmaskの影響、gainや時計変動、非Gaussian尤度、正規化、実機と画像の信頼度は未確認です。合成IQの検証では比較のため原本と一括FFTを保持し、蓄積器の状態容量と実行全体のRSSを区別します。

## 6. 次段階

相関器の実FFT処理に明示的な追加統計保存を接続し、独立したファイルで元のvisibilityと処理条件を追跡できるようにします。
