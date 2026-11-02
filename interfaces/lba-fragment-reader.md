# 旧LBASTD断片の実数偏波reader API

[179レポート](../docs/reports/179-lba-fragment-reader-api.md)。対象は178で確認した旧16byte UTC header、real 2偏波、2bit、LBASTD little-endian、供給公称8MHzの限定case。自動形式判定や全LBADR形式の対応ではない。

```python
from vsora_formats.lba import LBAFragmentRecording

reader = LBAFragmentRecording(
    "header.bin", "payload.bin", 8000,
    nominal_sample_rate_hz=8000000,
    recorded_pol_order=("R", "L"),
    chunk_samples=4096,
)
real_codes = reader.read_real_samples(1, 4097, recorded_pol_index=0)
for chunk in reader.iter_real_chunks(recorded_pol_index=1):
    real_codes = chunk["real_samples"]
```

`original_payload_offset_bytes` は元header直後を0とする供給元payload内のbyte位置。切出し後のheaderを作らず元headerを別fileで渡す。公称Fsは整数8000000だけ、offsetはboolを除く0〜2**53の整数、chunkは整数1〜65536。headerとpayloadは異なる通常file、header16byte/payload正の偶数byteを要求する。原本の取得・配置は[178手順](../validation/runs/stage178/README.md)を参照する。

記録偏波順を `("R","L")` または `("L","R")` で必ず供給し、各読込でindex0/1を指定する。PAはL,R、AT/HO/MPはR,Lという178の供給controlを保持する。偏波をI/Qへ見立てない。返却値は実数1次元 `np.int16`、DiFXの規約code `[8191,-8192,24575,-24576]`。単位名 `DiFX_s16_code` は物理ADC/電圧/gain/SEFD較正ではない。既存178の復号kernelを移したもので、scalar独立参照は検証workflowへ残す。

`read_real_samples(start_sample,count,*,recorded_pol_index)` は範囲内の整数start、整数count1〜65536だけを受ける。u16の4time tickへ整列し、必要なbyteだけseek/readする。最大payload readは32770byte/call、返却single-polは最大131072byte。これは全processのpeak RSS上限や実機速度・全夜throughputの保証ではない。constructorは識別のためpayload全体を一度読む。

`iter_real_chunks` は `start_sample=0, sample_count=None` を既定に、`real_samples/sample_index/read_ok/recorded_pol_index/polarization_label/nominal_source_sample_index/nominal_offset_s` を返す。最後の短いchunkも保持し、最後のyieldを再開した境界でもguardする。途中で消費を止めたiteratorの後続検査を実行したとは扱わない。`data/time/iter_frames` は提供せず、既存の複素SampleBuffer/sessionへ自動適用しない。

`nominal_start_utc` は元header+元byte offset×250nsの算術値をUTC9桁で表す。offset2byteが4time sampleで、公称8MHzに対応する。実時計1ns精度の測定ではない。`actual_sample_rate_hz=None/clock_accuracy_measured=False/station_id=None/band_edge_frequency_hz=None/sideband=None/is_complex=False` を維持する。ヘッダにない局ID・RF・sideband・実時計を補わない。異なる機材・長基線を既存600m profileへ合わせる操作もしない。

constructorは各instanceでheader/payloadのfresh SHA256を計算する。`expected_header_sha256/expected_payload_sha256` は両方だけを指定でき、lowercase64hexをfresh値へ照合する。caller digest/cacheによるhash省略ではない。`fragment_identity` はpathやinodeを公開せず、fragmentのSHA/byte/供給offset・公称時刻・偏波順を返す。未取得の元member/archive full SHAはnull、producer checksum認証はfalse。

各読込前後にresolved path/device/inode/size/mtime_ns/ctime_nsとheader内容SHAを検査し、開いたpayloadのfstatも照合する。全statを保つraw書換え、最後の検査後の変更、敵対的filesystemは証明できない。閉じた入力・trusted Python前提で永続file lockはない。同tickのraw変更が検出できない事前試験も保存した。headerは内容を再hashするため、statだけに依存しない。

検証再現は[179手順](../validation/runs/stage179/README.md)。新しい相関・解析信号化・画像・実clock較正はこのAPIの範囲外で、従来VDIF/SigMFの形式入口を変更しない。
