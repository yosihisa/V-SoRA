# 三角形の共通FFT標本からpowerを蓄積・正規化する

段階089の実験API。各三角形でU₃に使った標本集合と同じ集合から、三局のpower和を計算する。既存raw NPZ version1にはこの情報がなく、保存済みの局別診断powerから補わない。

## 同じ標本が必要な理由

局ごとの欠損があると、局単独の有効標本と三角形の共通標本は異なる。例えば6標本のうち局0のpowerが前半100・後半1、局1が前半欠損なら、三角形012で使えるのは後半3標本。局0の共通power和は3で、局0単独の全6標本の和303とは異なる。別の集合の値を分母にすると、段階085で調べた「同じ標本の比」にならない。

## 蓄積と入力

`vsora_correlator.bispectrum_accumulator.BispectrumAccumulator`は、既存のedge/paired/triple sumsに加え`common_station_power_sums[channel,triangle,3]`を返す。末尾はcanonical triangleのi,j,kの順。`consume`で与えた三局共通valid標本だけを使い、power・従来の和・countは成功時にまとめて更新する。FXでは新powerもRF昇順へ並べ替える。

固定storageの追加分は1cell当たり3×8bytes。上限4096channel×56三角形では5.25MiBで、標本列を全て保存する方式ではない。旧raw sidecarを選ぶ場合にもruntime内で蓄積するが、本段階ではversion1ファイルへは書かない。

## 正規化API

`vsora_correlator.bispectrum_power.normalize_common_power_bispectrum(result)`へaccumulatorまたはFXの`raw_bispectrum`を渡す。必要な配列はtriangles、common_sample_count、common_station_power_sums、distinct_sample_bispectrum、ordinary_common_sample_product。最大4096channel・56三角形・共通count100万まで。masked、非有限値、形状不一致、負power、無効countは拒否する。

三局のpower和をSᵢ,Sⱼ,Sₖ、共通FFT数をMとすると、観測powerはPᵢ=Sᵢ/M。返す比は `R=U₃ M³/(Sᵢ Sⱼ Sₖ)`。通常積も同じ分母で正規化する。powerの積を直接作ると中間overflow/underflowするため、仮数と2の指数に分けて計算する。float64変換で非有限になる値や非零成分が消える値、表現範囲外の比は拒否する。

| 出力 | 意味 |
|---|---|
| observed_power_normalized_u3 | 無次元のR。必ずu3_availableと併用する |
| observed_power_normalized_ordinary_product | 無次元の通常積。ordinary_availableと併用する |
| u3_available | M≥3かつ同じ集合の三局powerが全て正 |
| ordinary_available | M≥1かつ三局powerが全て正 |
| triangle_common_power_positive | 三局powerが全て正かどうか |
| channel_triangle_usable | supplied既存品質maskをコピー。未供給ならnull |
| normalized_u3_existing_quality_usable | u3_availableと既存品質maskの積。未供給ならnull |

未定義セルの複素0埋めは、0を測定した意味ではない。品質maskがfalseの数値も保持し、数値availableと品質usableを分ける。品質usableも独立性・誤差分布・天体検出を保証しない。

## 代数と数値範囲・制約

同じ固定maskを使い、各channelで局gainがwindow内の標本方向に一定なら、U₃とpower積のgain因子が相殺される。この有限データの代数は、Gaussianや独立性を仮定しない。maskをデータから選んだ場合の統計、未知のLO時間変化、比の不偏性は保証しない。

蓄積する生の和が既にunder/overflowした場合、後から正規化しても回復できない。段階085の電圧事前scale処理と同じdynamic rangeではない。ファイルの同一性も配列だけでは検査できない。既存visibility・重み・RMLを変更せず、符号反転p値や画像尤度へ自動投入しない。

## 模擬DSP照合

`python -m vsora_simulator.common_power_validation --output new-result`で固定9条件を実行する。3/4/8局、欠損・zero power・M<3・data依存maskを含み、実FFT後の同じ標本を直接電圧APIと照合する。最後の条件は4局、FFT32、19200block、2.048Mspsで0.3秒分の浮動小数点Gaussian IQ。257block刻みで処理する。実ADC・量子化・VDIF、基線の幾何遅延、LO差、OCXO安定時間、画像品質を検証した意味ではない。
