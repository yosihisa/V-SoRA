# 既知天体の局共分散と三次統計の複素rms尺度

## 既知の局電圧共分散

`sky_station_covariance(station_uvw_lambda, image, pixel_arcsec, receiver_sefd_jy)` は3〜8局の既知uvw座標、2〜128の正方形・非負のJy/pixel画像、正の受信機・背景SEFDを受け取る。SEFDは対象天体のpowerを含まない条件とする。マスク・負画像・数値範囲外を拒否する。

画素方向d=[l,m,sqrt(1−l²−m²)−1]に対し、局応答を `a_i(d)=exp(+2 pi i r_i dot d)` とする。天体共分散は `sum_p flux_p a_i(p) conjugate(a_j(p))`。既存visibilityの基線はr_j−r_i、Fourier位相は負なので符号が一致する。局応答と画素fluxの平方根によるGram行列は半正定値になる。

対角は対象天体の総fluxとなる。独立した受信機・背景SEFDを対角へ加え、既知総powerで単位対角へ規格化する。これは観測powerを推定・規格化した結果ではない。規格化後の対角は数値上も1へそろえる。beam・偏波・帯域応答は全局共通のscalarという仮定である。

## 三次統計の尺度

`known_bispectrum_moment_scale(S, M, target_scale=5)` は既知・正の局powerを持つS、3〜100万の独立proper Gaussian標本を仮定し、段階059の有限Mの平均・全共分散を使用する。

```text
B = E[U3]
Gamma_tt = E|U3_t − B_t|²
complex_rms_scale_t = |B_t| / sqrt(Gamma_tt)
Q_conditional = max(1,ceil((target_scale / complex_rms_scale_t)²))
```

段階057は一成分σを用いた天体無しの尺度だった。新しい量は複素rmsなので、天体無しの同じ分散を使ってもsqrt(2)だけ尺度が異なる。数値を同じSNRとして比較しない。

Qは同じS・uv・gainを持つ独立窓を繰り返す条件の量である。平均が数値0なら `zero_numeric_mean`、Qが上限10¹⁸を超えるなら `above_supported_count_limit` とし、Qをnullにする。どちらもゼロ秒・観測成功として扱わない。有限のQでも、秒数は同じモデルを繰り返す仮定の値で、地球回転を含む必要観測時間ではない。

Γだけでなくpseudocovarianceと、全実部の後に全虚部を並べた実共分散を返す。三角形同士の誤差を独立としない。複素rms尺度は角度・振幅比・GaussianなU₃尤度・検出確率・画像の情報量ではない。

## Cas A比較workflow

`workflows.bispectrum_known_sky_validation` は点源/Cas A形状、4/8局、spread/line/ringの600m配置、3受信機・背景SEFD、0.1/0.3/1/3秒の144条件を比較する。固定された仮想site35度/135度・1.42GHz・総flux1000Jy・64kHz channelを使用する。2026-10-02T08:00:00Zから300秒後の一つのsnapshotである。M=Bτは独立標本数の仮定にすぎない。

Cas Aは2017-08-13の1378/1750MHz参照画像を切り出し・非負画素の形状へ規格化したproxyである。1.42GHzの実際の画像やflux測定ではない。参照SHA、元周波数・日付、局座標、IERS/EOPの予測statusを保存する。

3つの既知SではM128・各8,192反復・seed76〜78で平均と全実共分散を照合する。積の反復配列は64反復ずつ処理する。4局と8局の代表条件の全実共分散を保存する。

## 未確認の実観測条件

実FFTの独立性、未知SEFD・power、時変gain、同じデータでのLO推定、局beam・偏波、RFI・品質選別、量子化、分布と画像化は未確認。gain・時計は短積分の中で既に補正済みとする。周波数混合は行わない。実相関器とRMLは変更しない。
