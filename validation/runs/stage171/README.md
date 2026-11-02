# 171：明示SigMF sessionの検証方法

比較元は文書170/製品169。原本・提供metadata・派生波形/数値JSON/配列/図は公開しない。このdirectoryは方法/合否の文章だけ。[report](../../../docs/reports/171-sigmf-aligned-session.md)と[契約](../../../interfaces/sigmf-session.md)を参照する。

## 再現する条件

保存済み `outputs/stage091-source-study/input/` の異なる模擬4局を使う。元ファイル全SHAを先に固定し、存在しない管理外directoryへ一度だけ派生する。091の取得/生成を再実行した結果ではない。131や公開単局CAMRASをこのfixtureに使わない。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_session_validation \
  --prepare --input outputs/stage091-source-study/input --output outputs/stage171-input
.verification-venv/bin/python tools/run.py workflows.sigmf_session_validation \
  --input outputs/stage171-input --output outputs/stage171-source-study
```

先頭7有効frameのpayloadから `2*byte-255` の整数尺度を固定し、供給epoch/Fs/RFは保存設定と対応させる。8番目のinvalid frameは採用しない。各dataは28672 complex sample。旧VDIF対照manifestは原本を参照し、scale71/FFT32/blocks128/2積分/開始0.002秒を使う。元の物理scaleの検証ではない。

旧169 wheelの独立prefixで対照の結果を先に保存し、新source/installedの全保存27field（metadataを含む）へ厳密一致を要求する。SigMFは独立直接畳込み/補間/FFTへRTOL1e-10/ATOL1e-7 ADC²で照合し、source/installedの27fieldも厳密一致させる。geometryは共有参照。新MC/実時計/実基線の試験ではない。

## 正式選択

対象は新SigMF session、既存clock/clock入力契約、pair検査CLI/identity、限定reader/SampleBuffer。新sourceとinstalledでcollectと全pytestを各一度選択し、新wheel/pipcheck/全製品byte+4assets、checkout外helperなしAPI/実CLI、両実Chromiumの保存診断28条件を検証する。旧151/168/169 prefixはbyte保持。数値配列・実行log・環境module origin・freeze/失敗は `outputs/stage171-*` へ保存する。正式実行中にsource/tests/tools/workflowsを変更しない。

retry保存を含むstage全体7200秒（attempt3前に改訂）、各attempt3600秒、full/GUI各900秒、reference各120秒、製品study追加peak128MiB（事前測定で改訂）/保存64MiB、全追加保存2GiB、空き10GiB reserve。ダウンロードなし。最終attempt3で全選択成功。両対象182/collect・full2434成功（各30300既存種別warning、除外0）、各27field一致と旧169 VDIF一致、105+4全byte、checkout外API/実CLI/両実GUI28条件を確認。非上書き4拒否は意図した非zero。初回/第二回の停止・全出力/freezeと補助の停止も管理外に保持し、成功を合算しない。
