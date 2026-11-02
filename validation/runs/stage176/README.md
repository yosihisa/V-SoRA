# 176：freshな元原本と保存shardの識別照合

[report](../../../docs/reports/176-sigmf-merge-source-binding.md)と[契約](../../../interfaces/sigmf-spectral-merge.md#明示した元原本とのfresh照合176)を参照。元raw/metadata/科学JSON/NPZ/図はGit管理外。

174の原本SigMF session/clockと2窓final-manifest/correlation shardをSHA固定して再利用する。175 installedのmerge_spectralでdefault SigMF/legacyのmerged.npzとreturn summary.jsonを保存し対照とする。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_merge_source_validation \
  --input outputs/stage174-source-study --source outputs/stage174-input \
  --baseline outputs/stage176-default175-baseline --output outputs/stage176-source-study
```

既定175全29field/returnを厳密一致、verifiedの数値はdefaultへ厳密一致。fresh原本data full SHA実呼出4回/9175040byte/1pass、子data hash0、source/installed全field/JSON一致。raw計算履歴の証明ではない。unitは小mock rawと人工spectral数値、studyは174完成shardを使う。新生成/相関/変換/取得/画像study fit/MC study0。

両新target/collect/full/wheel/pipcheck/105+4全byte/旧prefix全byte/checkout外API・実CLI/両実Chromium28条件まで正式選択。stage3600秒/attempt・全attempt7200秒/full・GUI900秒/study120秒/追加peak256MiB/保存64MiB/全追加2GiB/空き10GiB reserve/公開512KiB。code/補助/入力を凍結し、全worker終了後だけ修正して全選択再実行、失敗を保持し合算しない。正式初回で両対象115/collect・full各2515成功/各37716既存種別warning/除外0。default29fieldは旧175へ一致、verifiedを含む44field/return JSONはsource/installed全一致。105+4全byte/16module origin・byte/44依存版/実CLI・API/両実GUI28条件が成功。非上書き4件は意図した拒否。詳細な時間/peak/byte/制約はreportと管理外記録を参照。
