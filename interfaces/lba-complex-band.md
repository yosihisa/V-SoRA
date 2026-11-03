# LBA実数偏波の複素帯域view

[181レポート](../docs/reports/181-lba-complex-band-view.md)。元入力は[179の限定reader](lba-fragment-reader.md)。1つの実数偏波へ固定された有限digital operatorを適用する。R/LをI/Qとして混ぜず、実clockやRFを補わない。

```python
from vsora_formats.lba import LBAFragmentRecording
from vsora_formats.lba_band import LBAComplexBandView

source = LBAFragmentRecording(
    "header.bin", "payload.bin", 8000,
    nominal_sample_rate_hz=8000000, recorded_pol_order=("R", "L"),
)
view = LBAComplexBandView(source, recorded_pol_index=0, sideband="U")
values = view.read_complex_samples(1027, 4096)
for chunk in view.iter_complex_chunks():
    values = chunk["complex_samples"]
```

`source` はlive `LBAFragmentRecording`。元readerが各instanceでfresh hashし、各readをguardする。viewはそのlive objectを再利用するのでdata hashを追加しない。callerのdigest辞書や永続cacheは受けない。偏波index0/1と供給sideband `"U"` は必須。LSBや自動形式判定はこのAPIに含まない。PAの記録L,Rと他局R,Lは供給側で保持し、pathや局名から推定しない。

元payload byte offsetを $B$、fragment内のtime sample indexを $n$ とし、元source indexを $N_0+n=2B+n$ とする。固定処理は次の中心FIRである。

\[
z[n]=\sum_{k=-64}^{64}h_k\,2x[n+k]\exp\{-i\pi(N_0+n+k)/2\}.
\]

NCOは `[1,-i,-1,i]` をsource indexのmod4で引く。大きいindexの位相を浮動小数の大引数へ変換せず、seek/chunkで位相を再開始しない。元sample rateを変更せず、downsampleもしない。

$h_k$ は129tapの対称Kaiser窓（beta8.6）を使うlowpass。`scipy.signal.firwin(129, 7/32, window=('kaiser',8.6), fs=1)` のDC gain1に固定する。[公式firwin仕様](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.firwin.html)でcutoffはhalf-amplitude位置であり、参考保持帯域3/16 cycle/sampleとは異なる。実行時のSciPyは1.18.0。係数やNCOを実波形/真値へ合わせない。

factor2は実数cosineの正周波数成分の振幅規約を明示したもの。[FFT Hilbertの公式説明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.hilbert.html)と異なり、このAPIは固定有限FIRなので理想解析信号や完全image除去ではない。出力には有限filterの応答・鏡像漏れが残る。7固定周波数点のpass/image検査を連続帯域のsup保証へ広げない。3/16は参考保持帯域で、出力をhard maskする値ではない。

`read_complex_samples(start,count)` は整数count1〜16384、中心index64からN−65までの範囲だけを受ける。両側64sampleを元readerへ要求し、外挿/zero paddingを行わない。最大要求16512 real sampleで、元readerの65536上限内。単一readで返すcomplex128は最大262144byte。これは全process memoryや実機throughputの保証ではない。

元readerのN time sampleに対し、`first_valid_sample_index=64`、`stop_valid_sample_index=N-64`（exclusive）、`valid_sample_count=N-128`。`sample_count=N` と `nominal_start_utc` は元入力のindex0を表し、最初の有効出力へrebaseしない。FIR中心のindex $n$ が同じ名目時刻に対応する。実時計精度の測定ではない。

iteratorは `complex_samples/sample_index/recorded_pol_index/polarization_label/nominal_source_sample_index/nominal_offset_s` を返す。`start_sample=None` は64、`sample_count=None` は残りの全有効区間、chunkは整数1〜16384。`nominal_offset_s` は元fragmentのindex0からの公称秒である。`data/time/iter_frames` は実装せず、既存SampleBuffer/sessionへ自動適用しない。

単位名は `DiFX_s16_code_complex_band`。物理ADC/電圧/gain/SEFD較正ではなく、収録時の2bit量子化損失を回復した意味でもない。`actual_sample_rate_hz/局ID/RF` は未知のまま。供給USBを使うことはproducer認証やsideband測定ではない。公称8MHzをphysical clock欄へ代用しない。

各変換前後とiterator終端で、親fragment identity・型を保つ親context・viewの固定contextを検査する。公開属性の誤変更で偏波/時刻/単位が変わったまま処理しない。`filter_coefficients` と `processing_identity` はcopyを返す。親のraw全stat保持変更、最後の検査後の変更、trusted Python/file lock不在の限界を引き継ぐ。途中でiteratorを消費停止した後の検査を実施済みと扱わない。

この有限sample-domain変換は天体検出/fringe/実相関/Closure/画像検証ではない。実相関にはclock/geometry/単位を別契約で固定する必要があり、既存600m制限を外さない。検証条件と管理外出力は[181手順](../validation/runs/stage181/README.md)を参照する。
