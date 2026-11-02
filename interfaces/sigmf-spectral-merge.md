# SigMF補正窓の結合（175）

`vsora_imaging.synthesis.merge_spectral(paths, output)` は、[174の相関保存専用sequence](sigmf-session.md#相関保存専用sequence174)の補正済み窓を、time/channelを平均せずに結合する。`vsora-synthesis --merge-only --inputs ... --output merged.npz` はこの関数だけを呼び、Closure抽出や画像fitへ進まない。既定CLIの画像処理は従来のまま。

## 保存された識別の一致

SigMFは全入力で `input_format=sigmf_ci16_le` / `visibility_unit=ADC^2` を要求する。単一窓producerの `input_identity` はmanifest/clock/観測configのSHA256と、局順に並ぶmetadata/data pairのSHA256・byteを持つ。SHAはlowercase 64hex、byteはboolを除く正整数、data SHAは局間で異なることを要求する。

結合する窓間で局ID/順序とpair、clock SHA、観測config SHA、UTC原点が一致しなければ拒否する。各窓のmanifest SHAは異なってよく、各 `source_inputs[].input_identity` に残す。共通部分は `sigmf_original_identity` として保存する。mixed形式、識別の欠落/不正、既に結合したSigMFは出力前に拒否する。別recordingを結合する契約は追加していない。

既定modeは**保存された主張の一致**で、元raw/metadataを再open・再hashしていない。`original_files_rehashed=false` と `sigmf_identity_scope` を出力する。freshに計算するのは入力spectral fileのSHA。producer checksum認証、rawの現状態、正しい形の偽metadata、敵対的filesystemやfile lockを証明するものではない。閉じた入力を前提とする。rawのfresh識別/境界検査は上流171〜174の範囲である。

## 時刻・数値・容量

SigMFのUTC-Z原点は最大小数秒9桁で、供給観測configのstart_utcと1ns以内で一致させる。結合原点は9桁で保存する。これは供給値の算術・serialization整合で、実時計の1ns精度測定ではない。従来legacy入力の3桁serializationは変更しない。

全入力の局/geometry/source/unit/frequency axes、診断field集合、露出値、重複時刻/重複窓と2〜64入力/1M spectral cell上限は既存条件を維持する。SigMFは非負整数time×baselineの `valid_fft_count` を必須として保存し、未知の非diagnostic fieldは黙って捨てずに拒否する。countは独立標本数でも実効Mの較正でもない。複素平均、weight変更、noise/Closure/RML objective変更は行わない。

出力は後段へ渡すための結合データであり、この入口の成功だけで画像・天体検出・実FFT独立性・低SNR likelihood・confidenceを合格にしない。session-level SigMF画像pipeline/画像sequence/GUIの拒否は維持する。[段階175](../docs/reports/175-sigmf-spectral-merge.md)を参照。

## 明示した元原本とのfresh照合（176）

APIの `source_manifest`、`clock_model`、入力shard順の `input_manifests` を全指定した場合だけ、既存InputIdentityで元SigMF pair/controlをfresh hashし、既存guarded derived viewを窓manifestへ適用する。一部指定、legacy原本、画像CLIへの指定は拒否する。指定しない場合は175のrecorded-agreement modeをbyte/metadata/returnまで維持する。

```bash
vsora-synthesis --merge-only --inputs window-b.npz window-a.npz --output merged.npz \
  --source-manifest original-manifest.json --clock-model original-clock.json \
  --input-manifests window-b-final-manifest.json window-a-final-manifest.json
```

freshな子のpublic identity全4fieldをshardの保存identityへ一致させる。親/子の既存clock/pair/科学config契約に加え、shardのtyped観測config、FFT長/Fs/名目積分長、基線・周波数軸を子sessionへ照合する。caller SHA辞書や永続cacheを新しく受けない。原本data full SHAは親1pass、子data hashは0。`original_files_rehashed=true` と `input_identity_verification` にfresh親識別/診断と子診断を保存する。

検査境界はspectral読込前後・spectral hash後・出力直前。親/子のsmall JSON/metadata内容SHAと全stat検査を使う。検査後の変更や全stat保持raw変更を見逃す限界、閉じた入力/trusted Python、file lock不在は残る。spectralのload/hashは従来の閉じたfile経路であり、原本との計算履歴、配列がその原本から計算された証明、producer checksum認証を行う機能ではない。現物fileと保存された識別・設定の対応を検査するsnapshotとして扱う。画像fit/実時計/FFT独立性/画像尤度の新しい保証ではない。[段階176](../docs/reports/176-sigmf-merge-source-binding.md)を参照。
