# 明示SigMF sessionと時計整列相関

`correlate-aligned` と `vsora_correlator.aligned.correlate_aligned` は[限定SigMF reader](sigmf-input.md)をsession入力として選べる。形式省略時は従来の[VDIF session](session-manifest.md)を使う。これは処理形式の接続であり、実複数局・時計同期・天体検出の実証ではない。

## manifestと局

従来schema_version=1の共通keyに `input_format: "sigmf_ci16_le"` を明示する。`stations` の各要素は `{"id":"ST01","sigmf":"station-1.sigmf-meta"}` とし、全局を同形式へ統一する。pathはmanifestのdirectoryからの相対path、または絶対path。観測configの局ID/順序と一致する2〜255局を要求する。`vdif`、`station_numeric_id`、`decoded_voltage_scale` はSigMF局要素に書かない。

`voltage_unit` は `ADC` のみ。I/Q交互のsigned int16 little-endianをscale1で読む。manifestの正整数 `sample_rate_hz` と各metadataの供給Fs、観測configの `observation.frequency_hz` と供給RF中心をそれぞれ一致させる。RF中心未指定も拒否し、周波数を動かして既存profileへ合わせない。

VDIFの4096sample/frameによるFs/積分長制約はSigMFに課さない。FFT/shard容量、3秒・600m、FIR/補間と供給帯域guardの上限は維持する。混在形式や複数capture/channel等の非対応profileは拒否する。

## sample zeroと供給時計

[clock model](clock-model.md)で全局の `input_start_offset_s` と `actual_sample_rate_hz` を明示する。実rateは正の有限数・名目Fsから±1000ppm以内という既存整列条件に従い、bool等を拒否する。`max_abs_baseband_hz` は正の有限数で名目Fsの0.3以下。

SigMF相関の出力時間原点は小数秒9桁で保存する。各capture UTC-Z日時は、観測 `start_utc` ＋同局の `input_start_offset_s` と1ns以内で一致させる。この許容は**供給値同士の整合検査**であり、実UTC精度やclock同期が1nsと測定された意味ではない。sample位置は `(出力時刻−幾何遅延−input_start_offset_s)×actual_sample_rate_hz`。名目Fsから実clockを推定しない。

## 原本pairと出力

pair内のmetadata/dataが同じ実fileを指す場合、同じ実data fileや別fileへコピーした同一data SHAを複数局へ割り当てた場合は拒否する。異なるSHAだけで独立した実受信局と認定するものではない。

SigMF相関入口では `InputIdentity` を適用する。各runでmanifest/clock/観測config/各metadata/dataを新規SHA256計算し、dataのfull hashは各run一度。処理前後・各積分の前後でresolveとdevice/inode/size/mtime_ns/ctime_nsを検査し、制御JSONと各metadataは内容SHAも再確認する。途中変更は完成directoryへrenameせず、作成済みpartialに失敗状態を残す。

`input_identity.input_sigmf` は局IDごとのmetadata/dataのSHA/byteを保存し、local pathやmetadata全文を出さない。summary/visibility metadataには `input_format`、`sigmf_read_mode`、`sigmf_validation_scope` と検査量を記録する。VDIF8bitとは表示しない。出力は未較正ADC²。既定weight/SK/maskを変更せず、FFTの実独立性やnoise likelihoodを検証済みとも扱わない。任意のraw bispectrum保存は既存の有限和であり、実Closure画像復元の証明ではない。

閉じた入力と信頼されたPython呼出側が前提。data内容が全statを保持して変更されると、同じrunの境界検査は見逃し得る。SHAは生産者checksumの認証、永続file lock、敵対的filesystemの証明ではない。従来VDIF direct APIへidentityを自動追加したものでもない。

## 実行と範囲

```bash
.verification-venv/bin/python tools/run.py vsora_correlator correlate-aligned \
  --manifest outputs/my-sigmf-session/manifest.json \
  --clock-model outputs/my-sigmf-session/clock.json \
  --output outputs/my-sigmf-correlation --integrations 2 --start-offset-s 0.002
```

この機能を含むwheel環境は `vsora-correlate correlate-aligned` を使う。既存output/partialは上書きしない。`--sequential-input` は先頭から読み、既定はguard付きseek。helperなしの製品APIも使える。

通常 `correlate`、画像付きClosure pipeline・sequence、GUIのsession入口はSigMFを明示拒否する。[172のcorrelation-only pipeline](closure-pipeline.md#sigmfの相関保存専用入口)は、pilotから推定したrateで最終相関を補正する明示API/CLIまで対応する。公開CAMRAS原本は単局なので複数局sessionにはならない。原本・供給metadataを変更/複製して相関へ通さない。[取得配置と非公開方針](../docs/guide/public-voltage-data.md)、[段階171](../docs/reports/171-sigmf-aligned-session.md)を参照する。

173ではlive InputIdentity親から[派生session view](closure-pipeline.md#同じrunの派生identity173)を作り、pipeline内のfull data hashを1回へ集約する。private `_source_identity` にlive親を明示したSigMF direct subrunだけが対応する。通常のdirect呼出は引き続きfresh full hash。別clock/pair/科学configの再利用やcaller supplied SHAは拒否し、rawの全stat保持変更の盲点は残る。

## 相関保存専用sequence（174）

`process_sequence(..., correlation_only=True)` と `vsora-sequence --correlation-only` は、2〜64の非重複窓をpilot→rate推定→補正相関へ通して保存する。通常のVDIF画像sequenceは既定のまま。SigMF画像sequenceは明示拒否する。

SigMFには整数FFT blockを要求し、VDIFだけに4096sample/frame条件を適用する。窓数・spectral cell数・pilot被覆・3秒・600m・帯域/Nyquist・rate採否・三次統計容量の条件を維持する。correlation-onlyでは画像を作らないので画像用Fourier行列容量だけを検査しない。その他の相関容量上限は残る。

全sequenceでfreshな原本識別を一度作り、各窓のpilot/finalへguarded viewを渡す。窓間でも同じ局ID/順序と原本pair・clock/configを要求し、境界検査を維持する。`input_identity.sigmf_data_hash_file_reads` / `sigmf_data_hash_bytes` はsequence rootの累計。各窓のpipeline側は同じroot計数を繰り返し表示するため加算しない。別runはfresh full SHAで、全stat保持raw変更の盲点は変わらない。

完成時は `type=short_window_correlation_sequence`、`phase=correlations_saved`、`closures/rml/synthesis=null`。`windows[].relative_directory` から窓ごとのrate診断・相関shardへたどれる。`nominal_correlation_exposure_per_station_s` は指定積分長の合計で、mask後の実効露出や独立試行数ではない。従来の窓計画key `image_end_s` はこの入口でも最終相関窓の終了offsetを示し、画像を作った意味ではない。途中失敗はpartialと完了済みの窓を保持する。

公開CAMRAS単局を複製して複数局へ通さない。[段階174](../docs/reports/174-sigmf-correlation-sequence.md)の検証は保存された異なる模擬4局であり、実観測画像の検証ではない。
