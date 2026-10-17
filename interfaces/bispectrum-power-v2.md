# raw bispectrum version2：共通標本の電力を残す

## 何を保存するのか

三局 i, j, k の三角形では、同じ有効FFT標本を使って三辺の相関と各局の電力を計算する。欠測がある場合、各局が単独で使えた標本と三局で共通に使えた標本は異なる。[段階089の正規化API](common-bispectrum-power.md)は、この共通標本集合の電力を必要とする。

version1には三次統計を再構成する和はあるが、各局の共通電力は無い。version2は既存配列に common_station_power_sums を追加する。shapeは [time, channel, triangle, 3]、末尾は i, j, k、64bit浮動小数点、値は非負の電力和である。局電圧の単位がADCなら和はADC^2、sqrt(Jy)ならJy。ビット数や係数が同じという理由だけでADC単位をJyへ読み替えない。

## 保存と読込

save_bispectrum(path, data, metadata, schema_version=2) と明示する。既定は従来通りversion1で、共通電力を渡しただけでは自動昇格しない。load_bispectrum は1/2を読み、schema_versionを戻す。versionと配列集合が一致しなければ拒否する。

元のvisibilityのSHA-256、局ID、UTC原点、時刻・RF周波数、FFT長・標本周波数、単位、標本数、品質マスク、同一標本数の場合のedge和との一致を引き続き検査する。三角形の共通標本数が0なら共通電力も0である。電力が0なのに三次統計や通常積が非ゼロなら拒否する。これは全ての物理的整合性を証明する検査ではない。

同じファイルの上書きはしない。一時ファイルを使い、書込み失敗時には残さない。復号後の配列総容量は40MiB以下、time×channel×triangleは262144以下。新電力配列の最大追加payloadは6MiBで、ファイルヘッダや既存配列は別に容量を使う。共通電力が増えた分、同じ上限で保存できる総データ量は減る。圧縮後の小ささだけで読込上限を判断しない。

## 読み取った数値の意味

inspectionは時間・周波数セルを選択し、raw U3（ADC^6またはJy^3）と無次元の観測電力比を分けて返す。比は U3×M^3/(S_i S_j S_k) で、Sは共通標本の電力和、Mはその標本数である。有限標本の比は一般に母集団の比の不偏推定量ではない。

| 状態 | 意味 | JSONでの比 |
|---|---|---|
| missing_common_power_v1 | 旧版に必要な電力が無い | null |
| insufficient_samples | Mが3未満でU3を定義できない | U3比はnull。通常積の比は定義できる場合がある |
| zero_common_power | 三局のいずれかの電力が0 | null |
| usable_normalized_value | 数値を定義でき、既存品質マスクも通る | 数値 |
| masked_normalized_value | 数値は計算できるが既存品質マスクで除外 | 数値を残し、品質usableをfalseにする |

数値availableは数学的に定義できること、品質usableは既存flagを通ることを示す。どちらも「画像尤度へそのまま使える」という認定ではない。nullを0で補完しない。元visibilityの同一性確認は、FFT標本の独立性やマスク選別の影響を証明しない。共通電力の無いversion1を局単独の診断電力で埋めない。

## この段階の運用範囲

単独保存・再読込とPython/既存console CLIのinspectionを追加する。VDIFを扱う既存aligned producerはまだversion1で保存する。実際の相関ジョブによるversion2保存と日本語GUIの表示は次段階の対象である。LO補正、量子化、実機較正、低SNR画像尤度はこの形式追加だけでは解決しない。再解析のため元IQ/VDIFと時計・LO・品質処理の来歴も保持する。

inspection JSONは、版・共通電力・正規化可否のfieldを追加し、従来のraw値・単位・状態fieldを保持する。既存の全JSONを厳密に比較する処理では、このfield追加を差分として記録する。
