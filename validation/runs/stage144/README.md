# 段階144：観測SNRの選別条件

[レポート](../../../docs/reports/144-observed-snr-selection.md)、[各caseの採用/棄却と全科学値](reference.json)、[観測値/mask/各群統計107配列](arrays.npz)、[検証](verification.json)、[資源](measurements.json)。NPZは数値/booleanのみ、objectやpathなし。

sourceは `python tools/run.py workflows.snr_selection_validation --output <new-output>`。nativeはcheckout外から `python <checkout>/workflows/snr_selection_validation.py --output <new-output>`、runner/PYTHONPATHなし、OMP/OpenBLAS各1。wrapper自身はcheckoutが必要。

rho0/.45/1.6、M128、各4096、seed144000+index/batch32、fixed baseline01/phase triangle012。全試行の6MCSE対照と採用群の記述を分ける。N0の統計はnull、対応統計配列は保存しない。採用群や複数maskを独立追加試行へ数えず、不偏性/coverageや画像尤度を校正済みにしない。既存全回帰/wheel/GUIは138からの引用で新実行なし。
