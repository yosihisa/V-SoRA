# 174：SigMFの複数窓・相関保存

[report](../../../docs/reports/174-sigmf-correlation-sequence.md)と[契約](../../../interfaces/sigmf-session.md#相関保存専用sequence174)を参照。原本/供給metadata/派生波形/科学JSON/配列/図はGit管理外。

保存038の異なる模擬4局、先頭140有効frameを固定2*byte-255で一度派生。元の実ADC尺度ではない。4局×573440complex sample×4byte=9175040byte、各.28秒。原本SHAは管理外に固定し変更しない。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_sequence_validation \
  --prepare --input outputs/stage038-sequence/input --output outputs/stage174-input
.verification-venv/bin/python tools/run.py workflows.sigmf_sequence_validation \
  --input outputs/stage174-input --baseline outputs/stage174-legacy173-baseline \
  --output outputs/stage174-source-study
```

対照は173 installedのprocess_closure_session(..., correlation_only=True)で同じlegacy.json/clock.jsonを2回呼び、window-0000/.002秒とwindow-0001/.130秒へ保存する。pilot64/final.1秒/max100Hz/save_bispectrum=True。画像fitを作らない。

新sequenceは2窓、FFT32/pilot128blocks×64/start.002/step.128/final.1/constant/raw U3固定。各窓の補正visibilityは保存推定rate/shared geometryを条件に独立有限作用へRTOL1e-10/ATOL1e-7 ADC²内。MCSEなし。原本full SHAの実呼出4回/9175040byte/1pass、窓ごとに新hashしない。source/installed全fieldを一致させ、VDIF各窓のNPZ全42fieldは旧173へ厳密一致。8JSONはroot input_identityの共有計数だけを比較外とする。数値やNPZ metadataを除外しない。

新両target/collect/full/wheel/pipcheck/105製品+4assets全byte/旧prefix全byte/checkout外API・実CLI/両実Chromium28条件を正式選択。stage3600秒/attempt・全attempt7200秒/full・GUI各900秒/study120秒/追加peak256MiB/study保存64MiB/全追加2GiB/空き10GiB reserve/公開512KiB。正式中のcode/補助/入力を固定し、修正は全worker終了後だけ。attempt1の調整役はsystem Pythonのnumpy不足でworker開始前に停止し記録を保持、attempt2で全選択を実行。最終attempt2で両対象149/collect・full各2474成功/各37652既存種別warning/除外0。170fieldとsequence summaryのsource/installed一致、旧173 VDIF各窓42field一致、105+4全byte/23module origin・byte/checkout外API・実CLI/両実GUI28条件が成功。非上書き4件は意図した拒否。詳しい時刻/全失敗/peak/byteはreportと管理外の正式記録を参照。
