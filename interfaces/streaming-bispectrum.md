# 三次統計の追加の和を蓄積する実験API

## 平均visibilityだけでは足りない

三基線の積U₃には、辺の積の和と三辺を同時に掛けた和が必要です。平均visibilityを保存するだけでは、これらを後から再計算できません。FFT係数を全て保存する方法のほかに、必要な和を処理中に蓄積する方法があります。

## 入力と共通標本

`vsora_correlator.bispectrum_accumulator.BispectrumAccumulator(stations,channels,triangles=None)`で作り、`consume(spectrum,valid=None)`へ複素配列`[FFT block,channel,station]`を渡します。3〜8局、1〜4096channel、三角形は重複しない`i<j<k`です。1chunkは最大800万複素値。各三角形の保持数は最大100万です。

validは厳密なboolの`[block,station]`です。三角形の3局が全て有効なblockだけを、その三辺で共通して使います。二局ごとのvisibilityの有効集合とは異なる場合があります。三角形ごとに保持数も違うため、各基線の標本数をそのまま代用しません。masked array、不正値、数値範囲外を拒否し、失敗chunkで累積値を変更しません。

## 保存する和

辺をa=`xi conj(xj)`、b=`xj conj(xk)`、c=`xk conj(xi)`とします。channel・三角形ごとに、

- A：Σa、Σb、Σc（edge_sums）
- H：Σab、Σac、Σbc（paired_edge_sums、この順序）
- J：Σabc（triple_edge_sum）
- M：3局共通の保持block数（common_sample_count）

を蓄積します。`finish()`は一回だけ呼べ、通常の共通標本積`Aa Ab Ac/M³`と、

`U₃=(Aa Ab Ac−Hab Ac−Hac Ab−Hbc Aa+2J)/[M(M−1)(M−2)]`

を返します。M<3ではU₃を0として`distinct_sample_available=False`にします。これは測定したゼロという意味ではありません。配列のchannel・三角形の順序を維持します。

電圧単位をUとすれば、AはU²、HはU⁴、JとU₃はU⁶です。Jy較正、局power正規化、共分散や角度の信頼区間を求める処理ではありません。

## メモリと検証範囲

保持する数値状態は、F channel・K三角形に対し`112 F K + 8 K` bytesです。入力chunkと作業領域、Pythonのオブジェクト分は含みません。処理済みの電圧標本を状態に残さないため、数値状態の容量はblock数とともに増えません。

標本間独立・一定pair平均ならU₃の平均は不偏になりますが、この蓄積API自体は独立性やmaskの信号からの独立性を確認しません。FFTの入力共有、同じ記録からのLO補正、観測値による除外、gain変動は別に検証が必要です。現行相関器のvisibilityとRMLの重みには、この実験APIを適用していません。

[段階061レポート](../docs/reports/061-streaming-bispectrum-sums.md)
# FX処理からの明示的な収集

`FXAccumulator(..., collect_bispectrum=True)` は同じ非重複FFTブロックから追加統計を集め、finish結果の `raw_bispectrum` に返します。既定値Falseでは従来の返り値です。対象は3〜8局、FFT長2〜4096。追加統計の周波数順は既存visibilityと同じ昇順です。三局すべてのFFTが有効な集合だけを使用し、M<3または構成基線の重みが0のchannelは `channel_triangle_usable=False` です。品質flagは追加統計の数値を消去せず、利用可否に反映します。実FFT・品質選別の独立性は未確認です。段階063ではVDIF経路とファイル保存への自動接続は未実装です。
