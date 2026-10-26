# 段階136の保存pilot時間power診断

- [全科学JSON](reference.json)：24系列×28基線のstate、差引power、無制限ratio、入力/profile SHA。原本を共有する比較で独立試行ではない。
- [検証](verification.json)：両62既存対象、24 JSON byte一致、原本/12pilot/4profile、prefix/非上書き/旧package不変。新collectなし、2277は135の引用。
- [計測と全系列集計](measurements.json)：各source API/native CLIの有限秒数と全24系列の有限/null範囲。全夜/GPUのbenchmarkではない。
- [固定例の図](comparison.png)：high_a/channel4。0〜1に制限しない参考power比。

入力はGit外outputs/stage132-source-study/。各原本のt0.3 caseにあるpilotとrate-only.jsonをcanonicalとし、他1/3秒caseの全数値対応も検査した。正式出力はoutputs/stage136-source-study/とoutputs/stage136-installed-api/study/。原本の生成・相関・fitは追加しない。

sourceはtools/run.py workflows.saved_pilot_time_validation --reference 132study --record132 公開132/reference.json --output 新出力。導入側はcheckout外からtools/verify_saved_pilot_time_installed.pyを絶対指定し、24回の既存time_scatter CLIを実行。helperはcheckoutにある。元出力は再使用しない。

24系列がconditional_estimateでも672基線行の50比は未判定。622有限比には174負・148の1超があり、そのまま保存。powerの比は振幅保持率でも実機coherenceでもない。同pilotでrateをfitした依存、FFT/時間cell独立性、filter/量子化/変動、confidenceは未校正。production RMLやGUIを変更していない。
