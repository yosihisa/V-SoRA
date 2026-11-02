# 段階176：SigMF結合時の明示原本照合

- 作成日：2026-11-02
- 状態：完了
- 比較元コミット：`82fceee446df63e3f2c5089b621134fad81c5a9c`（175）

## 読者向け概要

175は窓に保存された識別情報同士を照合した。今回は元原本・clock・窓manifestを明示した場合だけ、それらの現在値をfreshに計算して保存識別へ結びつける。既存のInputIdentityと派生viewを再利用し、保存文字列だけの一致と現物fileへの照合を区別する。画像fitや元電圧の再相関は行わない。

## 1. 目的・対象範囲

merge_spectralのsource_manifest/clock_model/input_manifestsを全指定するopt-in APIとmerge-only CLIを追加する。既定175のSigMF/legacyの全field/metadata/returnを維持する。画像CLIとsession-level画像処理は追加しない。RML/Closureのnoise/weight/mask/目的関数、八条件は変更しない。

## 2. 完了条件

目的・入力SHA・固定許容・失敗/時間byteを実行前固定。親が元pair/controlをfresh hash、子は既存bind_sigmf_sessionでrawを再hashせず、そのpublic identity全4fieldとshard保存identityを一致させる。typed観測config/FFT/Fs/名目積分長/pair/frequency軸も子へ対応付ける。原本/clock/manifest/metadata/設定/軸差・読込途中変更・不完全指定を拒否し、既存出力を保持する。

新両source/installedの全field/JSON一致、既定175の全29field/return不変、verifiedの数値はdefaultと厳密一致、原本data hash実呼出4回/9175040byte/1pass・子data hash0を受入とする。両新target/collect/full/wheel/pipcheck/全byte/checkout外API・実CLI/両実GUI、公開監査/commit/push/実remote一致cleanまで完了条件。

## 3. 実際に行った作業

`synthesis.py` の明示引数から既存InputIdentity親とderived viewを作り、保存identity/config/FFT/軸を照合。入力読込前後・hash後・出力直前に既存原本guardを呼ぶ。verified出力だけoriginal_files_rehashed=trueと親/子診断を追加する。既定の記録一致modeは維持。

`test_sigmf_merge_source.py` は小さい相互に異なる模擬4局rawと派生manifest、人工のspectral数値を使用する。このunitの照合成功は、その数値がrawから計算された証明ではない。`sigmf_merge_source_validation.py` は175 helperを再利用してdefaultを確認後、174の実際の完成shardをfresh照合する。[契約](../../interfaces/sigmf-spectral-merge.md#明示した元原本とのfresh照合176)を参照。

## 4. 検証条件・結果

174の固定SigMF session/clock、2窓final-manifest/correlation shardを全SHA再利用。保存038の異なる模擬4局由来、供給nominal clock・固定code-unit尺度であり実ADC/SEFD較正ではない。175 installedからdefault SigMF/legacyの対照を保存する。原本生成/再相関/変換/取得0、新画像study fit/MC study/実基線0。既存fullの画像試験と分ける。131は76SHAを保ち再生成/再相関しない。

既定175の29field/returnは厳密一致。verifiedの数値と保存pairはdefaultへ厳密一致し、metadata/returnだけにfresh照合情報が増える。source/installed全fieldも一致を要求する。初回事前テスト46成功・64既存種別warning、1.67秒。事前study初回成功、原本data hash4回/9175040byte、子data hash0を確認した。人工metadataや原本差、config/FFT/軸差、読込途中の親変更、指定不足、legacy原本拒否を含む。数値許容は厳密一致、MCSEなし。truthへ係数/mask/grid/seedを合わせない。

workflowのmemory/time計測はverified処理も含む全体を正式前に覆うよう整理した。default部分とverified部分のoriginal_files_rehashed表示も別に記録する。正式初回の全選択が成功。事前の合格は正式件数に合算しない。

| 環境 | 対象成功 | full成功 / collect | full pytest時間 | 既存種別warning |
| --- | --- | --- | --- | --- |
| source | 115 | 2515 / 2515 | 583.16秒 | 37716 |
| installed | 115 | 2515 / 2515 | 586.06秒 | 37716 |

除外/skip0、全worker終了。既定175のSigMF/legacy全29field/returnは旧175対照へ厳密一致。verifiedはmetadata以外の全fieldと保存pairがdefaultへ一致し、新source/installedは3出力の計44field/各return JSONを厳密一致。原本data full SHAの実呼出は両studyで4回/9175040byte/1pass、各子data hash0。元voltageの再相関・変換や新画像study fitは行っていない。

新wheel SHA256は `f9b3b62ac6952282c75631e90c788290c66569532763b0d3c046e197ecc165d8`。105製品+4assetsのsource/wheel/installed全byte、16study module origin/byte、pipcheck、44依存版一致、checkout外helper不要APIと実CLIのNPZ/JSON一致が成功。非上書き4件の非zeroは意図した拒否で、既存出力SHAを保持。旧151/168/169/171/172/173/174/175 prefixは各旧wheel全byteと一致した。

両実Chromiumは各28条件/56JSON/672行/JS0/外部0/日本語390px。保存模擬診断のGUI回帰であり新SigMF画面の試験ではない。通常GUI151を更新/再起動しない。study/APIでRML/Closure moduleがimportされていないことも確認。

凍結1280file/453Python、固定入力212file、131原本76SHA、CAMRAS3SHAと旧原本/参照を保持。study追加peakはsource 1703936byte / installed 1966080byteで256MiB内。study全保存350862byteで64MiB内。正式後全追加保存集計609599774byte、空き41225310208byteで全追加2GiB/空き10GiB reserve内。新取得/変換/相関/MC study/画像study fit/実基線0。原本/metadata/派生数値の公開0byte。

[text validation](../../validation/runs/stage176/README.md)に方法を記載。原本/metadata/数値/図/log/freezeは管理外に保持する。

公開監査指摘0、文書リンク2357件で欠落0。10fileのstrict allowlistで公開し、対象外tracked1593fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

現物原本/子controlと保存識別のsnapshot照合であり、計算履歴、producer checksum認証、実時計やraw独立性の証明ではない。spectralのload/hashは既存の閉じたfile経路を使う。原本guardは読込前後/hash後/出力直前で、最後の検査後の変更や全stat保持raw変更の盲点、file lock不在、trusted Pythonの前提を残す。

実Cas A/未知実LO・gain・SEFD/beamRFI/実FFT独立性/低SNR画像尤度/全夜GPUは未検証。相対画像へ精密gain/絶対fluxを一律必須にしない。通常GUI151は更新/再起動せず、専用GUIは保存模擬診断の回帰。helper固定stage137/production_changed:falseを今回製品未変更と解釈しない。

## 6. 次段階

原本・科学shard・保存識別の対応を画像入口へ渡すなら、既存高SNR近似と時間周波数依存の適用範囲を含む独立受入/正式予算を先に固定する。八条件未成立の新画像尤度を形式接続で正当化しない。既存部品を重複実装せず、番号のための反復を増やさない。文書整理180/予定根本200。
