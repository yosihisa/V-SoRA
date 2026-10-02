# 周波数分解visibilityと較正

帯域平均前の内部NPZ：`vis_jy[time,channel,baseline]`、同形の逆分散`weights`、`uvw_lambda[...,3]`、0始まり`pairs[baseline,2]`、`times_s`、`frequencies_hz`。timeはmetadataのtime_origin_utcを基準とする秒、周波数は実RFのHz・昇順。無効サンプルはweight=0。有限complex値を保存する。これはFITS-IDIの複数channel実装ではない。

局応答は `g_i=a_i exp(i[phase_i+2π(f-fref)delay_i+2π(t-tref)rate_i])`、観測は `model * g_i * conj(g_j)`。位相・遅延・rateは基準局との差。rateの単位はHz（位相cycles/s）であり、物理的時計の秒/秒をそのまま表す値ではない。RF中心の位相と群遅延は別パラメーター。

較正JSONは参照局、振幅、位相、delay_s、rate_hz、基準時刻・周波数、解の適用範囲、検出指標と残差を保存。補正でvisibilityを局応答積で割り、逆分散重みはその絶対値の二乗を掛ける。範囲外への外挿は明示許可が必要。

段階007のsolverは一様なtime/frequency格子と既知の天体モデルを必要とする。[CASA fringe fitting](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.calibration.fringefit.html)の参照局FFT探索→全局最小二乗という流れを参考にした小規模参照実装。CASAの実装をコピーしていない。

- delayの曖昧周期は1/channel間隔、rateの曖昧周期は1/time間隔。探索窓はその半分未満。範囲外の真値はaliasして同じ測定値になりうるため、内部だけでは識別できない。
- 既知のfluxがない場合、絶対振幅を決められない。参照局の位相・delay・rateは0に固定。三角形等を含む識別可能な振幅グラフと全局への参照baselineを要求。
- FFTピーク・coherence不足、モデル不一致、探索境界、未収束は失敗にする。検出指標は実観測の誤検出率を保証しない。
- 時間平均や帯域平均で既に失われたcoherenceは後から回復できない。短い積分と十分なchannel分割で相関し、補正後に平均する。
- 分散性電離層、bandpass、偏波、時変clock drift、方向の異なる較正天体からの転送は未対応。
