# VDIF sessionの受渡し

Windows収録が完成していなくても、次のmanifestを持つEDV0/8bit complex VDIFをLinuxへ渡せる。ファイルは1局1thread1channel、4096sample/frame。frame時刻が全局で一致し、frameを消失させずinvalid flagで残すこと。欠落・開始時刻差・trailing partial integrationは現CLIで拒否する。

```json
{
  "schema_version": 1,
  "observation_config": "observation.json",
  "sample_rate_hz": 2048000,
  "fft_length": 128,
  "blocks_per_integration": 128,
  "integrations_per_shard": 64,
  "voltage_unit": "ADC",
  "phase_center_correction": true,
  "stations": [
    {"id": "ST01", "vdif": "ST01.vdif", "station_numeric_id": 1, "decoded_voltage_scale": 1},
    {"id": "ST02", "vdif": "ST02.vdif", "station_numeric_id": 2, "decoded_voltage_scale": 1}
  ]
}
```

観測設定には公開またはローカルで管理する局位置、天体ICRS位置、RF中心、UTC開始、画像grid等が必要。manifestの局順は設定と一致させる。`decoded_voltage_scale`はVDIF量子化値からADC counts等へ戻す倍率。これを設定しただけでflux較正にはならない。

- `voltage_unit=ADC` → 相関値単位`ADC^2`。自動的にJyとみなさない。
- `voltage_unit=sqrt(Jy)`は較正済み模擬電圧専用。実ADCに未確認の値を指定しない。
- native spectral **v2**は`visibilities`と明示単位を保存。Jyの場合だけreaderが`vis_jy`別名を提供。旧v1はJyとして読める。
- stream処理は1積分のIQと最大256積分のspectral shardを保持。成功時のみ`.partial`を最終directoryへrename。失敗時のpartial出力を完了扱いにしない。

## 較正点源のpilot

```sh
python tools/run.py vsora_correlator correlate --manifest manifest.json --output outputs/pilot
python tools/run.py vsora_correlator calibrate --input outputs/pilot/shard-00000.npz --point-flux-jy 1000 --output outputs/initial.json
python tools/run.py vsora_correlator correlate --manifest manifest.json --rate-calibration outputs/initial.json --output outputs/rephased
python tools/run.py vsora_correlator calibrate --input outputs/rephased/shard-00000.npz --point-flux-jy 1000 --output outputs/final.json
python tools/run.py vsora_correlator apply --input outputs/rephased/shard-00000.npz --calibration outputs/final.json --output outputs/calibrated
python tools/run.py vsora_imaging --input outputs/calibrated/visibility.fits --output outputs/image
```

`--point-flux-jy`は既知の**位相中心の点源**を仮定する。Cas Aの全基線に1000 Jy一定を入れて較正する用途には使えない。Cas Aは分解されるためshape modelを使う較正が必要。点源が用意できない場合の観測較正手順は未確定。

段階012では点源の代わりに`--model-config model.json`を指定できる。設定のsource.modelがcasaならL-band参照shapeを使用する。phase centerは収録設定と一致を要求。flux/shapeは**仮定したprior**であり、古い画像を使ったself-calibrationの成功だけでは未知の1.42 GHz画像を独立復元したことにならない。仮定fluxの誤りは利得へ吸収され、画像fluxもその仮定に従う。方位を含む絶対位相・位置も外部基準なしでは縮退しうる。

rate補正と較正の位相・時間原点・局順・入力単位は一致を要求。範囲外への適用は明示的な`--allow-calibration-extrapolation`が必要であり、長時間安定性を保証しない。初回pilotの推定で積分内損失を戻せないため、IQ再位相補正後に利得を再推定する。

## 制約

幾何補正は積分中央の周波数位相補正。有限FFT内のsampleずれや端の損失を除く処理はまだCLIに組込んでいない。時計整列APIは別モジュール。EOPはofflineの予測を含む。主ビーム、RFI、bandpass、偏波、実UTCの同期精度は未検証。

短時間・多数channelのまま長時間データを保存すると相関出力も大きくなる。pilotを短時間で取得し、rate/clock補正後に積分・帯域平均を長くする設計が必要。現FITS-IDIは1continuum channelのみ。
