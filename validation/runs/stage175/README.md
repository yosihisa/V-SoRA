# 175：保存SigMF窓の結合とUTC

[report](../../../docs/reports/175-sigmf-spectral-merge.md)と[契約](../../../interfaces/sigmf-spectral-merge.md)を参照。原本/metadata/数値出力/図はGit管理外。

入力は174 source-studyのSigMF/legacy各2完成correlation shard。raw/metadataを再生成・変更・再相関せず、SHA固定して再利用する。旧174 installed merge_spectralでlegacy2窓（逆順1/0）の対照merged.npzとreturn summary.jsonを保存する。画像fitを行わない。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_merge_validation \
  --input outputs/stage174-source-study --baseline outputs/stage175-legacy174-baseline \
  --output outputs/stage175-source-study
```

全数値は独立concat/sortへ厳密一致。旧legacy全NPZ field/metadata/returnは旧174へ厳密一致。SigMFの保存原本識別は一致だけを確認し、元原本を再hashしない。人工unit metadataのUTC .123456789Zとoffsetを整数ns計算へ1ns以内で照合、3桁負対照456789ns差を確認する。実原本epochを加工した試験ではない。新電圧処理/画像fit/MC study0。

両新target/collect/full/wheel/pipcheck/105製品+4assets全byte/旧151・168・169・171・172・173・174 prefix全byte/checkout外helper不要API・実CLI/両実Chromium28条件を正式選択。stage3600秒/attempt・全attempt7200秒/full・GUI900秒/study120秒/追加peak256MiB/study保存64MiB/全追加2GiB/空き10GiB reserve/公開512KiB。正式中code/補助/入力を固定し全worker終了後だけ修正、全失敗を保持して全選択を再実行し合算しない。正式初回で両対象96/collect・full各2496成功/各37652既存種別warning/除外0、29fieldとreturn JSONのsource/installed一致、旧174 legacyの全field一致。105+4全byte/4module origin・byte/44依存版/実CLI・API/両実GUI28条件を確認。非上書き4件は意図した拒否。詳細な時間/peak/byte/制約はreportと管理外の記録を参照。
