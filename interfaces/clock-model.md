# clock mappingと短chunk整列

時計モデルは、ファイルの先頭sampleをいつ測ったか、その後を一秒当たり何sampleで測ったかの対応です。公称値とは区別し、実測・推定・仮定のどれかを入力側で明示します。 [用語集](../docs/guide/glossary.md)。


```json
{
  "schema_version": 1,
  "max_abs_baseband_hz": 600000,
  "stations": [
    {"id": "ST01", "input_start_offset_s": 0.0, "actual_sample_rate_hz": 2048000.0},
    {"id": "ST02", "input_start_offset_s": 0.000001, "actual_sample_rate_hz": 2048000.2}
  ]
}
```

順番とidはsession manifestと一致させる。input_start_offset_sは観測設定のUTC原点から**入力sample0の実physical time**までの秒。USB到着時刻ではない。actual_sample_rate_hzはその短区間の実ADC rate。天体幾何を除いた時計値を指定する。段階009のeffective offsetは幾何を含みうるため、無条件で転用しない。

```sh
python tools/run.py vsora_correlator correlate-aligned --manifest manifest.json --clock-model clock.json --integrations 64 --start-offset-s 0.002 --output outputs/aligned
```

1～16384積分、全span3秒以下、time×channel×baseline100万cell以下、最大基線600m以下。必要なinput guardが存在する開始offsetを指定。65tap lowpassとfractional interpolationでbandを制限し、group delayを補償。位相中心へsample時間とRF位相を補正する。metadataにclock適用と単位を残す。

時計値の精度や時間変化を保証する機能ではない。raw ADCはADC^2のまま保存。LO/rateは別profileで推定してIQ補正できる。Closure画像化には高精度な利得較正を必須としない。bandpassと実測noiseの確認は引き続き必要。公称timestampと測定された時計値・仮定した値を区別する。

段階023で最小積分数を1へ変更し、段階027で3秒、段階029で16384積分と100万cell上限へ拡張した。rate-only JSONを使うLO補正と[Closure pipeline](closure-pipeline.md)を追加した。phase/amplitudeの高精度較正を必須とせず、ADC²から相対fluxの画像へ進める。


## 長記録の後方区間を読む

段階031から、必要な最初のsampleより64sample以上前にあるVDIF frameへseekする。65tap FIRの履歴と65tap sinc補間のsupportを確保してから計算し、global sample indexをsample0基準のまま保持する。入力時計式と時刻原点は変えない。

先頭header、ファイル全長、読んだframeの形式・局ID・順序・公称時刻を検査する。飛ばした前方区間を全header検査済みとはしない。原本全体のSHAはバイトの識別情報で、全headerが正常という証明ではない。`--sequential-input`で先頭から読む方法も選べる。これはprefixと読取範囲を検査し、未読の後方headerは検査しない。

metadata/summaryにvdif_read_mode、vdif_validation_scope、局ごとの読取開始sample、decoded frame数を残す。部分読取はsample時計や非線形LOの自動推定ではない。[段階031](../docs/reports/031-guarded-vdif-seek.md)を参照。
