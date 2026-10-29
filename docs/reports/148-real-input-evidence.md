# 段階148：実入力の根拠と取得環境を点検し、引渡し票を用意する

- 作成日：2026-10-29
- 状態：完了（読取り監査と人向け文書。実受信機・収録・画像化の検証ではない）
- 比較元コミット：8032cd922d63f55310ef96f941558b24397efc68（147）

## 読者向け概要

実データを解析へ渡すには、読める形式と、値をどのように確かめたかの両方が必要である。今回は現在のLinux実行contextで取得経路を確認できるかを点検し、既存4模擬原本について時計・scale・感度の情報源を照合した。

このcontextからはUSB一覧・device node・PATH上のRTL-SDR取得ツールを確認できず、実測は行っていない。物理装置が存在しない、Windows側でも使えない、と結論したものではない。138の一般確認表を再利用し、観測者が根拠を添付できる[実入力の引渡し票](../guide/real-input-handoff-template.md)を追加した。

## 1. 目的・対象範囲

145〜147の既知モデル参照から実入力へ戻り、実機・実記録・測定法が利用可能かを確認する。対象はLinuxから見えるmetadata、既存`load_session`/VDIF reader/InputIdentity/clock検査のコード、131 canonical4件のmanifest/clock/sidecarと公開生成記録、138/139の契約である。

138の[Linux入力確認表](../../interfaces/linux-input-readiness.md)は既に必要な一般情報を含むため、同等preflightやparserは作らない。新しい成果は、現在の取得contextの限定された記録、4原本の根拠目録、実測・推定・供給/計算・未測定を記入する人向け票である。機器open/初期化/収録/reset/設定変更、取得ソフトの導入、Windows収録、実解析の再実行は対象外。

## 2. 完了条件

可視性metadataを通常と承認付きread-onlyの両方で記録し、実機の不存在へ広げない。4原本の76SHAと44 metadataを照合し、供給値を実測へ変換しない。既存コードの行範囲/SHAとidentityの適用箇所・限界を残す。票はstrict manifest/clockから分け、新しい実行時ゲートとして扱わない。

対象外tracked、コード・設定・asset等451項目、過去個別report、原本を保持し、日本語report/索引/小容量記録、文書リンク・公開監査、公開名義commit/push・実remote一致までを完了条件とした。点検各120秒・公開記録2MiB以下を予算とした。

## 3. 取得contextの確認

コマンドを実行できるLinux contextのfilesystem metadataだけを読んだ。機器へ接続するコマンドを実行せず、serial・hostname・取得ツールの絶対pathは記録していない。

| 読取り項目 | 通常実行 | 承認付きread-only |
| --- | --- | --- |
| kernelのWSL marker | あり | あり |
| `/sys/bus/usb/devices`の可視性 | 確認できず | 確認できず |
| `/dev/bus/usb/*/*`の可視character node | 0 | 0 |
| PATHのlsusb/rtl_sdr/rtl_test/rtl_eeprom/rtl_tcp/usbip | 6種類とも見つからず | 同左 |
| SDRのopen/初期化/取得/reset・ソフト導入 | 未実施 | 未実施 |

[取得context記録](../../validation/runs/stage148/availability.json)に時刻・方法・scopeを保存した。二つの実行条件で見えたmetadataが同じという結果であり、二台の装置やsource/installed APIの検証ではない。WSL全体、Windows側の接続、別の取得機、既存実記録の所在までは確認していない。ツールがPATHに無いことを、あらゆる場所に未導入であるという主張へ広げない。

実観測データの保存先または取得環境をユーザーへ非同期で照会した。回答を待たなくても行える原本監査と文書整備を進め、実測や収録ができたとは記録していない。

## 4. 現在の4原本の情報源

131で選ばれた4件×19ファイルのSHAを現在のbyteへ照合し、manifest/clock/観測設定/8局sidecar、計44 metadataを読んだ。32 VDIFはdigestを確認しただけで、新しいheader検査やpayload decodeは行っていない。131当時の全header確認は過去記録の引用である。全記録は[原本と情報源](../../validation/runs/stage148/input-provenance.json)にある。

| case | 来歴 | 仮定SEFD (Jy) | 8局の供給decoded scale範囲 |
| --- | --- | ---: | ---: |
| high_a | 131の模擬生成 | 1000 | 25.2965〜248.1728 |
| high_b | 131の模擬生成 | 1000 | 16.0183〜160.6922 |
| weak_a | 131の模擬生成 | 10000 | 51.5693〜295.9854 |
| weak_b | 131の模擬生成 | 10000 | 68.1680〜543.4518 |

これらは既存metadataの読取り・要約であり、新しいADC測定値や感度推定ではない。全件で8局、公称Fs2.048MHz、FFT8、1024block、4096sample/frame、1520frame/局、名目3.04秒、電圧ラベルADCである。時計の供給offsetは全局0秒、供給actual rateは全局2048000Hz。UTC原点とRF1.42GHzも設定値で、PPS/sample0や実tunerを測った値ではない。

観測用設定のsource.modelがunknownでも、生成記録上の来歴は模擬である。観測設定seed42もraw生成seed131001〜131004とは別であり、seedはnoise/gain/LOを同時に変えている。sourceがunknownという文字列だけで実観測と分類しない。sidecarのclip/invalid情報も既存模擬writerの宣言として区別した。

## 5. コードの構造検査と、物理的根拠を分ける

6コードファイル・14関数/メソッドの行範囲とSHA、引用23ファイルのSHAを[一次コード記録](../../validation/runs/stage148/source-audit.json)に残した。製品関数は新しく実行していない。

- `load_session`は対応するkeys/局順・ID・単位・scale等を検査する。manifestを読めることだけでscaleやI/Qの物理的向きを証明しない。
- `iter_vdif_frames`は限定profile、先頭と読取範囲のheader/連続性/長さ等を扱う。公称sample rateで時刻を解釈し、seekで飛ばしたheaderを新しく検査したとはしない。
- 138のclock型検査は全局をbuffer構築前に確認する。数値型やguard内であることと、実sample0/clock精度は別である。
- `InputIdentity`は上位Closure pipeline/sequenceで使われる。runでfresh全byte hashを作り、stat境界と小さいmetadataの再hashを扱う。直接`correlate_aligned`自身に同じ管理を追加した機能ではない。SHAは全headerの証明ではなく、全statを保存する改変等の限界も残る。

原本保持・非上書き・partialと別出力への再処理は138/139を引用し、同じ試験を増やしていない。任意checkpointからの自動再開とも扱わない。

## 6. 引渡し票で具体化したこと

票には値の状態、根拠ID/測定法、不確かさ、有効区間、対応原本/局の欄を設けた。I/Q・単位、UTC/sample0、公称/実rate、RF/LO、設定変更・欠損/clip/RFI、SEFD/beam等を、原本のSHAと設定版へ結び付ける。未記入欄を模擬値で埋めず、未評価の精度を0としない。

票はstrict JSONの追加key指定でも、収録sidecarの新製品でもない。相対Closure＋RMLへ精密gain/絶対fluxを一律に必須とするものでもなく、未測定の条件がどの主張・誤差モデルに影響するかを明記する。[145の適用条件](../../interfaces/image-noise-applicability.md)を保持し、未知SEFDや時間依存を仮定値で隠してconfidenceを認定しない。

変更は人向け票、既存Linux入力確認表への追記リンク、本reportと索引、小容量[監査記録](../../validation/runs/stage148/README.md)である。

## 7. 検証・制約・次段階

凍結451項目と原本76SHAを保持した。新unit/target/full/collect/wheel/導入/browser/MC/raw生成/相関/fitは実行していない。新しい科学計算ではなくmetadata/AST/byte識別/文書の確認である。[正式監査](../../validation/runs/stage148/verification.json)に未実施を明記した。公開監査指摘0、文書リンク1970件で欠落0。

最新全回帰は138の両2321成功542.82/541.45秒・各30220警告/除外0、wheel103 file+4asset・両実GUI28worker/56downloadも過去の引用で、148の新合格に加算しない。147の両101対象・33配列一致も引用である。通常GUI138を更新・停止していない。

この監査は全recording/全ホストの調査ではなく、現在選ばれた4模擬原本と現在の実行contextに限る。実I/Q、物理sample0/UTC、実sample rate、実OCXO/未知LO、gain/SEFD/beam、RFI、実FFT独立性、実Cas A、低SNR画像尤度、全夜/GPUは未検証。

実測へ進むには取得できる環境または実記録の所在と測定法の根拠が必要である。149は実入力の情報が得られれば優先し、得られない場合は既存有限制限と原本byte数の予算を、性能実測や139の圧縮出力からの外挿と区別して点検する候補とする。同等preflight/試験を増やさず150の文書整理・専用根本レビューへ渡す。149以降と150自体は未実施。期限2026-11-06 15:00JST、追加reset禁止を維持する。
