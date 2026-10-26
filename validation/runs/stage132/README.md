# 段階132の未知LO・短積分相関記録

- [全条件と科学結果](reference.json)：131の原本識別SHA、全12条件のpilot/graph/rate/診断/相関/Closure/独立rank。保存数値はdtype/shape/SHAで識別。
- [実行計測](measurements.json)：source/導入の12所有CLI秒数。画像/GPU/全夜のbenchmarkではない。
- [検証集計](verification.json)：両50対象、両2263はcollectのみ、全保存数値の直接照合、prefix/非上書き、core/wheel不変。全回帰は121を引用。

大容量原本はGit管理外outputs/stage131-source-study/、処理結果はoutputs/stage132-source-study/とoutputs/stage132-installed-api/study/。原本は再生成せず、131/referenceの全76SHAで照合した。source/導入は同一条件の再現で独立24観測ではない。画像はこの4原本では未実施。既存対象試験の小さなRML fixtureは回帰している。

実行はverification環境Pythonからsource tools/run.py workflows.short_integration_matrix --raw-root outputs/stage131-source-study --reference131 validation/runs/stage131/reference.json --output 新出力先、導入側はcheckout外でtools/verify_short_integration_installed.pyを絶対指定して同じ原本とsource結果を照合。PYTHONPATHなし。元の出力先は再使用しない。

個々のCLI logとローカルprefix情報はGit管理外。公開記録から個人pathと出力依存SHAを除き、元入力全SHA・各適用profile対応・全科学値の照合を別に検査した。未処理null/処理後0制約/取得停止を区別する。実機や低SNR画像尤度の検証ではない。
