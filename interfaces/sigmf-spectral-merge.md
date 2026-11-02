# SigMF補正窓の結合（175）

`vsora_imaging.synthesis.merge_spectral(paths, output)` は、[174の相関保存専用sequence](sigmf-session.md#相関保存専用sequence174)の補正済み窓を、time/channelを平均せずに結合する。`vsora-synthesis --merge-only --inputs ... --output merged.npz` はこの関数だけを呼び、Closure抽出や画像fitへ進まない。既定CLIの画像処理は従来のまま。

## 保存された識別の一致

SigMFは全入力で `input_format=sigmf_ci16_le` / `visibility_unit=ADC^2` を要求する。単一窓producerの `input_identity` はmanifest/clock/観測configのSHA256と、局順に並ぶmetadata/data pairのSHA256・byteを持つ。SHAはlowercase 64hex、byteはboolを除く正整数、data SHAは局間で異なることを要求する。

結合する窓間で局ID/順序とpair、clock SHA、観測config SHA、UTC原点が一致しなければ拒否する。各窓のmanifest SHAは異なってよく、各 `source_inputs[].input_identity` に残す。共通部分は `sigmf_original_identity` として保存する。mixed形式、識別の欠落/不正、既に結合したSigMFは出力前に拒否する。別recordingを結合する契約は追加していない。

これは**保存された主張の一致**で、元raw/metadataを再open・再hashしていない。`original_files_rehashed=false` と `sigmf_identity_scope` を出力する。freshに計算するのは入力spectral fileのSHA。producer checksum認証、rawの現状態、正しい形の偽metadata、敵対的filesystemやfile lockを証明するものではない。閉じた入力を前提とする。rawのfresh識別/境界検査は上流171〜174の範囲である。

## 時刻・数値・容量

SigMFのUTC-Z原点は最大小数秒9桁で、供給観測configのstart_utcと1ns以内で一致させる。結合原点は9桁で保存する。これは供給値の算術・serialization整合で、実時計の1ns精度測定ではない。従来legacy入力の3桁serializationは変更しない。

全入力の局/geometry/source/unit/frequency axes、診断field集合、露出値、重複時刻/重複窓と2〜64入力/1M spectral cell上限は既存条件を維持する。SigMFは非負整数time×baselineの `valid_fft_count` を必須として保存し、未知の非diagnostic fieldは黙って捨てずに拒否する。countは独立標本数でも実効Mの較正でもない。複素平均、weight変更、noise/Closure/RML objective変更は行わない。

出力は後段へ渡すための結合データであり、この入口の成功だけで画像・天体検出・実FFT独立性・低SNR likelihood・confidenceを合格にしない。session-level SigMF画像pipeline/画像sequence/GUIの拒否は維持する。[段階175](../docs/reports/175-sigmf-spectral-merge.md)を参照。
