# 段階139の有限運用記録

[段階レポート](../../../docs/reports/139-finite-operation-recovery.md)に目的と解釈を記す。[全科学値](reference.json)、[正式検証](verification.json)、[単独workerの時間/メモリ](measurements.json)を保存する。実行原本はGit管理外の131-source-study、参照は138-source-study/high_aで、全76SHAを公開131へ照合した。VDIFを再生成しない。

sourceは `python tools/run.py workflows.finite_recovery_validation`、導入版はcheckout外から `python <checkout>/workflows/finite_recovery_validation.py --mode installed` に、`--raw-reference <131-source-study> --record131 <131-reference.json> --reference138 <138-source-study/high_a> --output <new-output>` を渡す。既存出力へ重ねない。導入workerにはrunner/PYTHONPATHを渡さず、製品module所属をprefixへ確認する。wrapper自身はcheckout内である。

個別stdout/stderrとmodule絶対pathはGit管理外に保持する。公開結果にはローカルユーザーpathを含めない。CLIも検証wrapper内でInputIdentityを使うが、製品CLIへSHA機能を追加したわけではない。本文の全2321回帰/wheel/GUIは138の引用で、139は再実行していない。
