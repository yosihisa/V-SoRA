# 173：派生identityと同じ固定入力の照合

[report](../../../docs/reports/173-sigmf-derived-identity.md)と[契約](../../../interfaces/closure-pipeline.md#同じrunの派生identity173)を参照。原本/提供metadata/派生波形/科学JSON/配列/図は全てGit管理外。

172のinputと完成studyの全SHAを固定して再利用する。新生成/取得/変換はしない。原本038/091/13176SHA/CAMRAS3SHA/171参照も保持する。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_identity_reuse_validation \
  --input outputs/stage172-input --baseline outputs/stage172-source-study \
  --output outputs/stage173-source-study
```

固定4局70frame、FFT32/pilot128blocks×64/start.002/final.1/max100Hz/constant/raw U3。digest_fileの実呼出を数え、full data SHA4回/4587520byte（旧12回/13762560byte）を厳密に確認。総I/Oや実機速度の試験ではない。source/installed全field一致、172 SigMF39非metadata field/3科学metadata/8JSON一致、VDIF42field/8JSON厳密一致。除外する追跡値だけを事前固定し、raw_bispectrum.bytesは実fileへ照合。数値許容を緩めない。独立有限作用は保持した172 helperを使うためinstalled studyにはcheckout helperが必要で、製品APIには不要。

両新target/collect/full/wheel/pipcheck/105製品+4assets全byte/checkout外API・実CLI/両実Chromium28条件を正式選択。旧151/168/169/171/172 prefixを保持。stage3600秒/full・GUI各900秒/reference120秒/製品study追加peak256MiB/保存64MiB/全追加2GiB/空き10GiB reserve/公開512KiB。正式中はcode/補助/入力SHAを固定し、修正は全worker終了後だけ。正式初回の全選択成功。両134対象/collect・full各2459成功/各32332既存種別warning/除外0、全84fieldのsource/installed一致、保存172への科学field一致、105+4全byte、checkout外API・実CLI/両実GUI28条件。非上書き4件の非zeroは意図した拒否。事前2停止を保持し合算しない。
