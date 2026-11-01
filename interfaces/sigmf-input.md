# 限定SigMF入力と単局整列API

`vsora_formats.sigmf.SigMFRecording` は、既存の公開ci16_le原本を8bit VDIFへ変換せず読むための限定API。形式上の用語は[公式SigMF仕様](https://sigmf.org/)を参照する。本APIは全SigMF仕様への対応や準拠認証を主張しない。

## 対応する記録

同じdirectoryの `name.sigmf-meta` と `name.sigmf-data` を組にする。dataはI/Q各signed16bit little-endianの交互成分で、読込後は元整数を厳密表現するcomplex128。scale1・未較正ADCであり、Jyへ変換しない。

| 条件 | 限定APIの契約 |
| --- | --- |
| core version | `1.x.y` の文字列 |
| datatype / channels | `ci16_le`、単一channel |
| nominal sample rate | 明示した正の有限数。boolは拒否 |
| capture | 1個、`sample_start=0`、明示UTC-Z日時 |
| sample origin | dataset先頭0。`offset` と `global_index` は0のみ |
| headers / trailing bytes | 0のみ。`core:dataset` の指定自体とmetadata-onlyは非対応 |
| extensions | 任意拡張は未解釈。未知のrequired拡張は拒否 |
| metadata | 最大1MiB、重複JSON keyを拒否 |
| data | regular file、空でなく、4byteの整数倍 |
| chunk | 1〜65536sampleの整数。既定4096 |

別名日時やpointingなどの補助情報は `record.metadata` に保持するが、意味・精度・時計モデルを推定しない。RF中心は供給があれば有限値として `center_frequency_hz` に保持し、未指定はNone。局IDは生成しない。metadata-only、複数capture/channel、非対応datatypeは明示拒否する。

## 有界frame読込

```python
from contextlib import closing
from vsora_formats.sigmf import SigMFRecording

record = SigMFRecording("data/raw/public/camras-crab/crab-giantpulse.sigmf-meta")
with closing(record.iter_frames(start_sample=2000001)) as frames:
    frame = next(frames)
    voltage = frame["data"]
    sample_index = frame["sample_index"]
    supplied_time = frame["time"]
```

開始位置は原本sample indexの整数で、範囲内・非負を要求する。実読込開始はchunk境界へ切り下げる。最後の短いchunkは捨てず、追加sampleも作らない。`time` は供給capture日時＋sample index／供給Fs。これらの数値を保持しても、実UTCやsample時計の精度が分かった意味ではない。

`valid` はbyteとして読めたsampleの構造上の状態であり、天体信号・RFI・受信機品質の判定ではない。annotationsを品質maskへ変換しない。呼出側が途中で読むのを止める場合はiteratorをcloseする。

dataのdevice/inode/size/mtimeを検査し、検査後の置換・途中変更や短readを拒否する。これは暗号学的な原本同一性の保証ではない。`core:sha512` が記載されても自動検証しておらず、`checksum_verified` はFalse。必要な原本SHAとmetadataの固定は上位の取得・検証手順で行う。既存InputIdentityはpipeline/sequence側の別機能で、本API自身の保証ではない。

## 単局SampleBufferへの明示入口

```python
import numpy as np
from vsora_correlator.aligned import SampleBuffer

# この例は供給Fsを名目identity mappingとして使う。実測clockではない。
buffer = SampleBuffer.from_sigmf(
    "data/raw/public/camras-crab/crab-giantpulse.sigmf-meta",
    actual_rate=20000000, chunk_samples=4000,
)
try:
    values, valid = buffer.query(2000000.25 + np.arange(256))
finally:
    buffer.close()
```

actual_rateは呼出側が明示し、正の有限数・供給Fsから±1000ppm以内を要求する。両境界を含む。seek_inputはbool。既定のVDIF constructorは従来どおり使える。単局のFIR/補間への入口であり、session manifestや相関CLIのSigMF対応ではない。

FIR/補間は入力波形を変える。実受信帯域のguardや時計精度に対する科学的な適用条件は別に確認する。原本の先頭ではFIR支持不足がmask=False/値0となり、記録範囲を超えるqueryは拒否する。単局を複製して実基線やClosureを作る用途には使わない。
