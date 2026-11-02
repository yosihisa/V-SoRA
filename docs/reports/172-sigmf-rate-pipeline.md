# 段階172：SigMFのpilot・rate推定・補正相関

- 作成日：2026-11-02
- 状態：完了
- 比較元コミット：`297e6e434be9da97de3cc08ba8aaa667dad68bfa`（171）

## 読者向け概要

171では、16bitのSigMF原本を供給時計で整列して相関する入口を追加した。今回は短いpilot（周波数差を推定するための先行相関）を作り、その相関から得た局rateで同じ入力を補正して最終相関を保存する。既存の推定手順へ新形式を接続し、画像処理は追加しない。保存済み模擬4局で処理の対応を検証するもので、実観測画像の成功ではない。

## 1. 目的・対象範囲

`process_closure_session(..., correlation_only=True)` と `vsora-closure-session --correlation-only` を明示SigMFへ接続する。171のci16_le/全局ADC/scale1、局ID/順序、供給Fs/RF/UTCとclock sample zero、原本pair契約を継承する。画像付きpipeline・sequence・GUI・通常correlateのSigMF形式追加は選ばない。供給値の1ns整合許容を実時計1ns精度としない。

SigMFのpilot/final長は整数FFT blockを要求し、VDIFの4096frame制約を流用しない。0.1〜3秒final/3秒pilot/600m/帯域guard/時間範囲/Nyquist/rate採否を維持する。定数/線形という既存モデルであり、新しい任意LO位相回復や実clock推定ではない。

## 2. 完了条件

実装前に管理外purpose、入力SHA、固定許容・予算を記録。旧171 installedの保存VDIF対照へ全NPZ field/決定的JSONを一致させ、新SigMFはsource/installed一致と独立有限作用へRTOL1e-10/ATOL1e-7 ADC²で照合する。小合成unitで非frame grid、2rate model、途中変更partial、非上書き、非対応画像/sequence/GUI拒否、metadata symlinkのsiblingを検証する。

両新target/collect/full、新wheel/pipcheck/全製品+4assets byte、checkout外API/実CLI、両実Chromiumを正式選択とする。原本・提供metadata・派生数値をGitへ出さず、コード・方法/合否の文章だけを公開する。

## 3. 実際に行った作業

| ファイル | 変更 |
| --- | --- |
| `closure_pipeline.py` | SigMF correlation-only、形式別FFT grid、metadata絶対path clone、外側+subrun hashの集計 |
| `test_sigmf_pipeline.py`（correlator） | 実pipelineの定数/線形、非frame final、拒否/途中変更/clone、20MHzの次元probe |
| `test_sigmf_pipeline_gui.py`（UI） | 既存analysis GUI jobがSigMF画像処理へ進まない実API確認 |
| `test_bispectrum_storage.py` | loaderの新keywordを受ける既存stub。容量拒否条件を維持 |
| `sigmf_pipeline_validation.py` | 保存模擬入力の限定派生、旧VDIF対照、独立有限作用 |
| 契約/案内/索引/計画 | 対応入口、3回のhash、未検証項目を同期 |

詳しくは[利用契約](../../interfaces/closure-pipeline.md#sigmfの相関保存専用入口)、[SigMF session](../../interfaces/sigmf-session.md)。外側とpilot/finalの計3instanceで各dataを1回ずつhashし、全pipelineでは3passとなる。完成summaryは内訳と実読込byteを記録する。長記録へ1pass reuseを実現したものではない。全stat保持のdata変更の盲点は継承する。

## 4. 検証条件・結果

保存038の異なる模擬4局の原本全SHAを先に固定。各先頭70有効EDV0/8bit frameを固定 `2*byte-255` のci16へ一度派生した。各286720 complex sample、公称0.14秒、供給Fs2.048MHz。元の供給scaleやSEFD/物理ADCの較正ではなく、固定71のcode-unit参照。元原本を変更/再生成しない。131の76SHA、CAMRASの3SHA、171参照も保持する。公開実単局を複製しない。

FFT32、pilot blocks128×64（cadence .002秒/span .128秒）、開始.002秒、final .1秒、max_rate100Hz、constant、save_bispectrum=Trueを固定した。独立参照は直接Kaiser65tap畳込み、2048sample単位のsinc/Hann補間、RFと保存推定rateの位相、unitary FFT平均。geometryと保存推定rateは供給参照で、EOPやrate推定のbias/coverageの独立検証ではない。truthへ格子/係数/mask/seedを合わせず、生成真値をfitterへ渡さない。

事前studyのvisibility最大差は約2.3554e-12 ADC²で固定許容内、旧171 VDIFの42保存fieldとsummaryが厳密一致。事前対象115成功（94.10秒）、GUI拒否1成功（1.85秒）。20MHz/小数秒のtestはmockでpilot到達までの次元/clone検査であり、実20MHz波形の数値試験とはしない。実pipelineの非frame gridは2.048MHz/.100015625秒で検証する。

最終attempt2の全正式選択が成功。初回の収集停止を合算しない。

| 環境 | 対象成功 | full成功 / collect | full pytest時間 | 既存種別warning |
| --- | --- | --- | --- | --- |
| source | 116 | 2441 / 2441 | 561.66秒 | 32260 |
| installed | 116 | 2441 / 2441 | 559.45秒 | 32260 |

除外/skip0。両studyの独立visibility最大差は約2.3554e-12 ADC²で固定許容内。SigMF/VDIFそれぞれ42保存field（metadataを含む）をsource/installedで厳密一致させ、旧171 VDIF42fieldとsummaryにも一致。22製品moduleのorigin/byteを確認した。

新wheel SHA256は `2b037ef940fca2b0692c3aa4c694fb1f5e6127f52c643880e70f8edad2051792`。105製品file+4assetsのsource/wheel/installed全byte、pipcheck、checkout外helperなしAPIと実CLIが成功。非上書きworker4件の非zeroは意図した拒否で、既存成果物SHAを保持した。両実Chromiumは各28条件/56JSON/672行/JS0/外部0/日本語390pxを確認。旧151/168/169/171 prefixは各旧wheel全byteを保持した。

凍結1270file/445Python、原本131の76SHA/固定038原本/CAMRAS3SHA/171参照を保持。製品study追加peakはsource 97021952byte / installed 97185792byteで256MiB内。正式後の管理外保存集計621389771byte・実空き44103643136byteで全追加2GiB/空き10GiB reserve内。新取得0byte、公開原本/提供metadata/派生データ0byte。


### 正式初回の収集停止

attempt1は相関器とGUIの新試験が同名test_sigmf_pipeline.pyだったためimport名が衝突し、collection1error/実試験0で停止した。全worker終了後にGUI側をtest_sigmf_pipeline_gui.pyへrenameし、内容は変えず全正式選択をattempt2で再凍結した。初回log/freeze/旧名の試験を管理外に保持し成功を合算しない。

### 171の記録訂正

171の管理外集計補助がlog先頭のfile別2816 warningsを拾っていた。保存された両full footerは2434成功/30300 warningsであるため、171レポートと管理外検証記録を30300へ訂正した。元logと訂正前記録を保持。科学配列・試験成功数・条件は不変で、171の数値試験を今回の成功へ合算しない。今回の集計はfooterを行頭から照合する。

詳細は[text validation](../../validation/runs/stage172/README.md)。実行log/失敗/部分出力/freeze/科学JSON/配列は全て管理外。

公開監査指摘0、文書リンク2319件で欠落0。14fileのstrict allowlistで公開し、対象外tracked1573fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

この新studyでは画像fit/MC study/実基線/新取得0。全回帰内の既存画像試験と、新規実観測研究を混同しない。CAMRASは410MHz単局のまま。受信機チームは実記録なし、OCXO/構成/保存形式検討中の回答を維持し再照会しない。

実Cas A・1.42GHz・未知実LO/gain/SEFD・beam/RFI・実FFT独立性・低SNR画像尤度・全夜GPUは未検証。外部初期LO範囲、pilotの安定性/alias、noiseでの探索false-positive未校正という既存制約も残る。相対画像へ精密gain/絶対fluxを一律必須にしない。native RMLのw項/固定同種同cell共分散、047JSON/044jointを読まない点は変更しない。

通常GUI151の旧prefixを更新/再起動しない。両実GUIは保存模擬診断の回帰で、新SigMF入力画面の検証ではない。helper固定stage137/production_changed:falseを172製品未変更という意味にはしない。

## 6. 次段階

次はSigMF sequenceへ残るFFT grid・原本identity共有・窓間原本一致・容量・画像に渡る契約をreviewする。新画像fitを選ぶ場合は目的と独立受入を改めて固定し、単なる形式追加から実画像復元の成功を主張しない。実アンテナ別電圧の新観測ID/最小byte/利用条件が確定した場合は少量取得を別途選ぶ。番号のための小変更を反復せず、次文書整理180/予定根本200を維持する。
