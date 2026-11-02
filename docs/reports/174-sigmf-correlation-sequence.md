# 段階174：SigMFの相関保存専用sequence

- 作成日：2026-11-02
- 状態：完了
- 比較元コミット：`fbdf744d78a020c7072f159c8e7e4a0a42a3194b`（173）

## 読者向け概要

173までは1つの短時間窓をpilot（周波数差推定用の短積分列）、rate推定、補正相関へ通せた。今回は同じ原本の複数窓を順に処理し、原本識別を共有しながら保存する。窓を画像へ合成する処理は追加しない。実際の複数受信局やCas A画像の成功を示す段階ではない。

## 1. 目的・対象範囲

明示 `correlation_only=True` のsequence API/CLIにSigMFを接続する。既定VDIF画像経路の条件・結果構造を保持し、SigMF画像pipeline/画像sequence/GUI/通常correlateは拒否する。原本pair/局ID・順序/clock/単位/RF/時間範囲と既存のrate採否を継承する。

## 2. 完了条件

目的・契約・入力SHA・固定許容・失敗保持・時間byte予算を実装前に管理外へ固定。2〜64非重複窓、整数FFT block、既存相関容量を維持する。新source/installedの全保存field一致、旧173 VDIFの各窓全42NPZ field一致、独立有限作用とのRTOL1e-10/ATOL1e-7 ADC²内、原本data full SHAが4局で計1passとなることを確認する。新両target/collect/full/wheel/pipcheck/全byte/checkout外API・実CLI/両実GUIまで正式選択し、公開監査/commit/push/実remote一致・cleanで完了とする。

## 3. 実際に行った作業

- `sequence.py`：bool opt-in、形式別FFT格子、窓間形式別identity一致、correlation-only保存、partial失敗保持。画像用Fourier行列容量だけをこの入口で除外する。
- `closure_pipeline.py`：live親の共有を許可し、各窓のhash計数はroot累計の反復と明示する。
- `test_sigmf_sequence.py` と既存sequence/pipeline/UI tests：原本変更/短入力/容量/型/既存出力/画像非実行/既定拒否を確認する。mock loaderの追加keywordも受ける。
- `sigmf_pipeline_validation.py`：既定70frameと開始.002秒を保つkeyword拡張。`sigmf_sequence_validation.py` は保存140frameの2窓を照合する。
- 契約・案内・計画・索引・text validationを更新。詳細は[SigMF契約](../../interfaces/sigmf-session.md#相関保存専用sequence174)。

## 4. 検証条件・結果

保存038の異なる模擬4局から、先頭140有効frameを固定 `2*byte-255` でci16へ一度派生した。原本の再生成ではない。元の供給scale/物理ADC/SEFD較正とも呼ばない。Fs2.048MHz、各573440complex sample/.28秒、4局data合計9175040byte。FFT32/pilot128blocks×64、開始.002/.130秒、final.1秒、step.128秒、max100Hz、constant、raw U3を実行前固定。供給nominal clockであり未知実clockを推定していない。

保存推定rateと共有geometryを条件に、172の独立有限畳込み・補間・FFT作用を開始offsetだけ明示して再利用する。最初の窓は従来helperの既定呼出とも厳密一致。MCSEなし、同じ有限模擬標本であり独立実観測試行ではない。truthへweight/係数/mask/格子/seedを合わせない。

事前対象31成功・12208既存種別warning、69.10秒。事前studyは初回成功、各窓最大差2.355403620993077e-12 / 2.822205621511423e-12 ADC²で固定許容内。旧173 installedで同条件のVDIF2窓を別に保存し、各窓42NPZ field全てと8JSONを照合。JSONだけはstandalone/shared rootのinput_identity計数を区別し、そのroot key以外を一致させる。NPZのfield/metadata/bytesを除外しない。

### 正式実行と失敗保持

attempt1は依存関係のないsystem Pythonで調整役を起動したため、numpy import時点で停止した。開始worker0、数値試験0。起動log/freeze/初回helperを保持し、全worker未開始を確認後、検証用Pythonへ変更して全正式選択をattempt2で実行した。製品・入力・数値許容は変更せず、初回の成功を合算しない。

attempt2の全選択が成功。初回の起動停止を消さず、合格に合算しない。

| 環境 | 対象成功 | full成功 / collect | full pytest時間 | 既存種別warning |
| --- | --- | --- | --- | --- |
| source | 149 | 2474 / 2474 | 577.38秒 | 37652 |
| installed | 149 | 2474 / 2474 | 583.50秒 | 37652 |

除外/skip0。source/installedで2形式×2窓の全NPZ fieldと独立参照2field、計170fieldを厳密一致させ、各sequence summaryも一致した。旧173 VDIF対照は各窓42NPZ field全てとroot identity計数以外の8JSONが一致。両SigMF studyでfull SHA実呼出4回/9175040byte/1passと、全窓direct subrunのdata新規hash0を確認した。各窓の独立作用との差は上記と同じで、固定許容内。

新wheel SHA256は `5510d4e290064a01d9ffe2c53d0b8bbfacd2f026d82727bb17fe3f810d1f3a89`。105製品+4assetsのsource/wheel/installed全byte一致、23study moduleのorigin/byte、pipcheck、44依存版のsource/installed一致、checkout外helper不要APIと実CLIが成功。既存出力への非上書き4件の非zeroは意図した拒否で、既存成果物SHAを保持。旧151/168/169/171/172/173 prefixを各旧wheel全byteと照合した。通常GUI151は更新/再起動していない。

両実Chromiumは各28条件/56JSON/672行、JS0/外部0/日本語390pxを確認。保存模擬診断のGUI回帰であり新SigMF入力画面ではない。全worker終了済み。

凍結1278file/451Python、固定入力146fileと131原本76SHAを保持した。製品study追加peakはsource 201175040byte / installed 122445824byteで256MiB内。study保存各64MiB以下。正式後管理外の追加保存集計634196286byte、実空き42417909760byteで全追加2GiB/空き10GiB reserve内。原本data派生9175040byte、取得0byte、実基線0、新画像study fit0。原本・metadata・派生データの公開0byte。

[text validation](../../validation/runs/stage174/README.md)に再現方法を記載し、原本・提供metadata・派生波形・科学JSON/配列/図・log/freezeはGit管理外へ保持する。

公開監査指摘0、文書リンク2338件で欠落0。15fileのstrict allowlistで公開し、対象外tracked1580fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

同じrunの閉じた入力・逐次処理・trusted Pythonが前提。小metadata/controlは内容SHAとstatを再確認するが、dataが全statを保って変わる盲点は残る。永続cache/file lock/敵対的filesystem証明ではない。別runはfresh full hash。hash読込量は波形を含む総I/Oや全夜throughputの測定ではない。

実基線/新取得/新MC study/新画像study fit0。既存全回帰の画像試験とは分ける。131原本76SHA、CAMRAS3SHA、038/091/171/172原本・参照を保持し、131を再生成/再相関しない。CAMRASは単局のまま。実Cas A/未知実LO・gain・SEFD/beamRFI/実FFT独立性/低SNR画像尤度/全夜GPUは未検証。native RMLのw項/固定同種同cell共分散/047JSONや044jointを読まない条件は不変。相対画像へ精密gain/絶対fluxを一律必須にしない。

通常GUI151は更新/再起動しない。専用両実GUIは保存模擬診断の回帰で、新SigMF画面の検証ではない。helper固定stage137/production_changed:falseを今回の製品未変更と解釈しない。

## 6. 次段階

画像への接続を選ぶ場合は、複数窓の局/時計/単位/原本identityと画像入力の具体的契約、独立受入、正式予算を先に固定する。新実観測原本は観測ID/最小byte/利用条件が具体化してから少量取得する。番号のために同じcodec反復を増やさない。文書整理180/予定根本200を維持。
