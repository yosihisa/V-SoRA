# VDIF sessionの受渡し

manifestは各局のVDIFファイルと共通の処理条件をまとめたJSONです。相関器へ入力を渡す一覧表として使います。sample rate・RF周波数・記録値の単位を別々に指定します。 [用語集](../docs/guide/glossary.md)。


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

`correlate`の幾何補正は積分中央の周波数位相補正。sample整列を行う`correlate-aligned`は[clock規約](clock-model.md)の別入口を使う。EOPはofflineの予測を含む。主ビーム、bandpass較正、偏波、実UTCの同期精度は未検証。RFIは下記の模擬診断を追加した。

短時間・多数channelのまま長時間データを保存すると相関出力も大きくなる。pilotを短時間で取得し、rate/clock補正後に積分・帯域平均を長くする設計が必要。段階013では`apply`が`spectral-visibility.fits`も保存し、channel別weights/flagsを保持する。channel別重みが異なる場合はcontinuumへの近似を行わず、`continuum_exported=false`にする。

画像CLIは較正済みspectral NPZと多channel FITS-IDIを直接読める。RF帯域内でflux一定の狭帯域MFS参照処理。raw ADCは拒否する。CLEANは各点の正確なuvw応答（w項と全視野境界を含む）を使い、応答cacheを約16MiBまでに制限する。大規模な高速gridding/GPU処理は未実装。

## channel品質診断

manifestに任意の`spectral_quality`を追加すると、周波数別の雑音重みとRFI診断を有効にできる。

```json
{
  "channel_weights": true,
  "min_sk_blocks": 128,
  "sk_bounds": [0.3, 3.0],
  "exclude_rf_ranges_hz": [[1419999999, 1420000001]]
}
```

瞬時FFT powerのspectral kurtosis(SK)を計算する。局別有効FFT数がmin_sk_blocks未満ならSKによる判定を行わず、`diagnostic_station_sk_eligible=false`を保存。SKのplaceholder=1を測定値と解釈しない。固定範囲[0.3,3]は試作上の仮定であり、実機のfalse alarmを保証しない。

`diagnostic_station_flags`のbitは1=有効powerなし、2=SK下限、4=SK上限、8=指定RF範囲。局channelがflagなら、その局を含むbaseline/channelの重みを0にする。visibility値は残す。power、SK、eligible、局別有効FFT数をshardに保存し、較正後も診断値を保持する。power単位はmetadataのdiagnostic_power_unitを参照し、ADC段階のpowerをJyへ自動変換したとは扱わない。

channel_weights=trueでは2M/(P_i P_j)を使用する。独立receiver・弱いsource・独立FFTの近似。filterや強い共通天体による分散・相関を完全には扱わず、bandpassそのものを較正する機能ではない。短いpilotではSKの統計量不足が起こるので、手動除外または別の長い診断区間を使う。

通常の積分は4096sample frameの整数倍または約数。例えば2.048MHzでは2048sampleで1msに分割できる。
