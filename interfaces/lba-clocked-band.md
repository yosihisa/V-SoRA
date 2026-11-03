# 明示clockモデルによるLBA複素帯域query

[182レポート](../docs/reports/182-lba-clocked-band-query.md)。[181のlive複素帯域view](lba-complex-band.md)と既存 `clock.interpolate_samples` を接続する、短区間の有限参照APIである。

```python
from vsora_correlator.lba_alignment import LBAClockedBandView

# source は既存の live LBAComplexBandView。
# model は下記10項目を全て明示したcallerモデル。
aligned = LBAClockedBandView(source, model=model,
                             invalid_source_ranges=[(1050, 1052)])
result = aligned.query(query_times_s)
samples, valid = result["complex_samples"], result["valid"]
```

modelは `schema_version=1/station_id/time_origin_utc/input_start_offset_s/actual_sample_rate_hz/rf_band_edge_hz/output_center_frequency_hz/phase_offset_rad/clock_provenance/rf_provenance` の全10key。未知key/欠落/非有限値/数値boolを拒否する。clock/RF provenanceは `supplied_model/estimated/measured` のcaller宣言で、認証・測定の確認ではない。元viewのactual clock/局ID/RF未知属性は変更しない。

`time_origin_utc` はUTC-Z、最大9桁のfractionを持つepoch labelを保持する。queryはこの同じepochからの相対秒。元headerのnominal epochを実clockへ読み替えず、model epochとnominal epochを自動同一視しない。実UTC精度の測定ではない。

Rを明示actual sample rate、aをinput start offset、tをquery secondsとし、元fragment内positionを `p=(t-a)R` とする。Rは正有限かつ元nominal±1000ppm、aとtは絶対値3秒以下。queryは増加finite1次元1〜2048点である。lo=`floor(min p)-32`、hi=`floor(max p)+34`（exclusive）の中心sampleを181viewから読み、既存radius32補間を適用する。読込中心数は最大16384、返すcomplex128は最大32768byte。これは全process memoryやthroughputの測定ではない。

181は中心FIRで既に元indexを保つため、SampleBufferの別65tap causal filterや+32群遅延補償は追加しない。両側64sampleのFIRと補間のsupportを全て確保し、余分な上端guardも要求する。Nを元sample数として、pの下端は96以上、上端はN−97未満となる。この保守的な範囲を外れるqueryは外挿せず拒否する。有効先頭へのrebaseはしない。

Eを供給USB RF端、F0を出力RF中心、N0を元payload byte offsetの2倍、φを明示phase offsetとする。補間後の値へ、次のcycleで `exp(i*2π*cycle)` を掛ける。

```
cycle = ((E - F0) + R/4)*t - R*a/4 + (N0 mod 4)/4 + φ/(2π)
```

これはUSB正周波数成分のRF端oscillatorをmodel epochに置く、明示したcaller規約である。R/4というdigital mixerの物理shiftをclockと対応付け、元NCOの整数位相原点を保持する。`abs(E+R/4-F0)<=R/16` を要求する。大きいN0を浮動小数の位相へ変換せず、定数cycleと最終cycleをmod1へ減らす。scalar libm/complex演算で1点とbatch分割の丸めを揃える。既存LO/rate profileを自動適用しない。

有限FIRの周波数応答と鏡像漏れ、有限補間の応答は残る。この式を連続信号の厳密再構成、一般anti-alias処理、実clock/LO推定、物理電圧較正としない。出力unitは `DiFX_s16_code_complex_band` のままで、ADCやJyへ変更しない。

`invalid_source_ranges` は元real time-sample座標のsorted非重複半開整数区間。caller宣言をFIR supportへ展開し、既存補間のvalid伝播へ渡す。invalid出力は0/valid=false。宣言なしは録音の欠落・RFI不在を証明しない。未使用の余分guardだけのinvalidと、実際に和へ含むsupportのinvalidは区別する。

各query前後で元processing identityとtyped model/invalid宣言を検査する。model/identityはcopy、元reader/identity/guardを再利用し追加full data hashやcaller digest/cacheを導入しない。親の全stat保持raw変更・最終guard後の変更・trusted Python/file lock不在の限界を維持する。

戻りはcomplex_samples/valid/source_positions/query_times_s/complex_input_start/complex_input_count/processing_identity。data/time/iter_frames/sessionへの自動入口ではない。既存600m guard/clock/単位/VDIF/SigMF/RMLの契約を変えず、長基線LBAを600m profileへ偽装しない。実4局の未知clock/RFはquery前に拒否する。

検証は新しい小人工fixtureの有限参照で、実録音の整列・fringe・実相関・画像を主張しない。[条件と再現手順](../validation/runs/stage182/README.md)を参照する。
