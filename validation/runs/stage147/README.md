# 段階147：同pilot rate fitと独立雑音評価

[レポート](../../../docs/reports/147-rate-fit-reuse.md)、[全512組・profile/失敗graph](reference.json)、[33数値配列](arrays.npz)、[正式検証](verification.json)、[資源](measurements.json)。NPZは数値のみでobject・pathを含まない。失敗試行のfit配列は保存せず、成功indexと対応付ける。全試行oracle配列は失敗を含む256行/条件である。

sourceは`python tools/run.py workflows.rate_fit_reuse_validation --output <new-output>`。nativeはcheckout外から`python <checkout>/workflows/rate_fit_reuse_validation.py --output <new-output>`、runner/PYTHONPATHなし、OMP/OpenBLAS各1。workflow自身はcheckoutを必要とする。

3局/64cell/.008秒/1channel、真値局rate0/7/−11Hz、基線複素平均exp(i[.3,−.7,1.1])、quadrature σ=.5/1、各256。乱数はSeedSequence([147,condition,trial,role0train/1eval])。独立雑音と既知分散は生成仮定で、実FFTの測定ではない。rate fitへtrainのv/w/t/pairsだけを渡し、上限50Hz・既定8/8/chisq3を維持。全試行oracleの0残差/期待power1、成功群独立evalの推定後Dirichlet予測との差を固定6MCSE+1e-11で検査する。学習側の差や改善は記述のみ。失敗・負・1超を捨てない。

元raw131、IQ/VDIF/FIR、未知実LO/gain/SEFD、画像を処理していない。実機coherence/保持率・画像confidenceの校正ではなく、158推定失敗を保持した有限Gaussian visibility比較である。既存138全回帰/wheel/GUIは引用のみ。

Git外の正式目的・凍結・全ログは`outputs/stage147-preparation/`、実行出力は`outputs/stage147-source-study/`と`outputs/stage147-installed-study/`、継続記録は`outputs/development-continuation.md`に保存。
