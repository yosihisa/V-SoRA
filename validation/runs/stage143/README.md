# 段階143：保存pilotのrate学習/未使用cell比較

[レポート](../../../docs/reports/143-pilot-rate-holdout.md)、[全科学値/入力SHA/元row番号](reference.json)、[検証](verification.json)、[時間/容量](measurements.json)を保存する。派生24 NPZ・完全CLIログ・module絶対pathはGit管理外。

sourceは `python tools/run.py workflows.pilot_rate_holdout_validation --reference <132-source-study> --record132 <132-reference.json> --output <new-output>`。nativeはcheckout外から `python <checkout>/workflows/pilot_rate_holdout_validation.py --mode installed` に同じ引数を渡し、runner/PYTHONPATHなし、OMP/OpenBLAS各1。wrapper自体はcheckoutを必要とする。

元132の12pilot同値を照合してcanonical4件だけ解析する。学習375cell/未使用374cellのparityと端除外、50Hz上限、DC評価は事前固定。別rawの独立評価でも、fit依存やconfidenceの校正でもない。旧全pilot profileはidentity照合のみ、truthを推定/回転へ渡さない。最新全回帰/wheel/GUIは138の引用で、新しく実行していない。
