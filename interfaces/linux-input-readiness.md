# Linux解析側へ渡す入力と原本追跡の確認

実RTL-SDR/OCXO観測を将来取り込む際の確認表である。**現時点で実機を検証したという宣言ではない。** Windows収録の実装、未知の時計を復元する新API、任意のVDIFを自動変換する機能は追加していない。

段階148で、値の出所・根拠・不確かさ・有効区間・原本対応を記入する[実入力と測定根拠の引渡し票](../docs/guide/real-input-handoff-template.md)を追加した。人向けの観測記録で、manifest/clockへの追加keyや新しい収録sidecar parserではない。[148の確認](../docs/reports/148-real-input-evidence.md)では、現在の実行contextから取得経路を確認できたかと、4模擬原本の供給値を分けて記録する。

## 三種類の確認を分ける

| 確認 | 現在のソフトでできること | これだけでは分からないこと |
| --- | --- | --- |
| 同じ原本か | 閉じた入力に毎run新しいSHA-256を計算し、段階間のstat・metadata SHA変化を検査 | 収録時の物理時刻やI/Qの向き、全headerの正しさ |
| 読める構造か | 対応profile・局ID・読んだ範囲のframe連続性・長さ、設定の型/単位/局順を検査 | 部分seekで飛ばしたheader、実sample clock精度、天体検出 |
| 物理的に何を測ったか | 記録された仮定を使って整列・LO差推定・相関を計算 | 時計値/scale/beam/SEFDの実測根拠、未知の弱信号での成功 |

SHAが一致しても、取り違えた設定と原本の組を一緒に保存していた場合の物理的正しさまでは確認できない。下の情報を実測・推定・仮定・未確認に分けて観測記録へ残す。

## 相関器が現在消費する入力

| 情報 | 保存する場所 | なぜ必要か・制限 |
| --- | --- | --- |
| 局とファイルの対応、公称sample rate、FFT、decoded scale、単位 | [session manifest](session-manifest.md) | VDIFの読み方とADC²の尺度を決める。較正前のADCをJyと取り違えない |
| UTC原点、局位置、phase center、RF中心 | 観測設定JSON | 波長単位の基線と幾何遅延を計算する。VDIFだけで全てを補えない |
| sample0の物理時刻、短区間の実sample rate、通過帯域 | [clock model](clock-model.md) | 同じ時刻の電圧を合わせる。USB到着時刻で代用しない。真値を与えた模擬対照と実測を区別する |
| 短pilotから求めた局別LO/rate差と有効区間 | [Closure pipeline](closure-pipeline.md)のrate profile | sample時計とRF発振器のずれは別。検索範囲外の折返しや速い位相変動を自動保証しない |
| 失われた区間、有効flag、RFI選別 | VDIFのinvalid flag、設定、相関のmask | 穴を測定された0電圧として扱わない。現在はframe欠落・途中の形式変更を自動補修しない |

現在の受渡しprofileはEDV0・8bit complex・1channel・thread0で、sessionは4096sample/frameを要求する。これは本リポジトリの対応範囲であり、VDIF全体の規格の範囲を説明したものではない。readerは指定された公称sample rateを使ってframe時刻を解釈する。ファイル長だけから実ADC rateを測定したことにはならない。

時計JSONの数値にはboolや文字列を入れない。例えば帯域欄の`true`はHzではない。138以前はPythonの数値変換により1 Hzとして受け付けられ、周波数の採否が変わる反例があった。現在は全局分の設定をbuffer構築前に拒否する。正しい数値でも、指定した帯域が実際の受信帯域と一致するかは別途確認する。

## 別途残す観測記録

以下は**現parserへ任意の追加keyを入れる指定ではない**。strictなmanifest/clockとは別の観測ノートや添付記録に残す。これらを読む新しい収録sidecar製品は未実装である。

- I/Qをどの順・符号で記録したか、RFの上側/下側がどちらへ対応するか、その確認方法。complex型で読めることだけでは物理的な向きを証明できない。
- 公称と実sample rateの根拠、PPS等とsample番号の対応、最初のsampleの時刻誤差、時計を一定と扱える区間。OCXOのRF位相安定性も別に確認する。
- 収録中の中心RF、gain、sample rate、アンテナ/偏波、配線、設定変更や再起動の区間。ひとつの一定設定の原本へ黙ってつなげない。
- ADC量子化・クリップ・欠測・RFIの状態、scaleの決め方。実SEFDやbeamが未測定なら、仮定した値と区別する。
- 原本の識別情報、コピー後のSHA、処理ソフトの版、使用したmanifest/clock/rate profileと出力。公開リポジトリには私的な局住所・連絡先・認証情報を置かない。

Closureは局ごとの一定した複素gainに強いが、必要な入力情報を全て不要にするものではない。幾何、時計、周波数の対応、方向に依存するアンテナ応答、弱い信号での雑音モデルは、それぞれの適用範囲を確認する。

## 原本保持・失敗・再開

既存`InputIdentity`は、同じrun内で入力のpath・device/inode・長さ・mtime/ctimeを境界検査し、小さいmetadataを再hashする。VDIFはrun開始時に全byteを新規hashする。攻撃的に全statを保存する改変などを完全に検出する仕組みではなく、全header検査の代わりでもない。[画像統計の契約](image-statistics-contract.md)も参照する。

元VDIFを変更せず、新しい出力先で処理する。既存の完了出力や`.partial`があれば、その場所への再実行は拒否する。失敗したpartialを成功へ名前変更せず、失敗記録を保持して原因を直し、別の出力先を選ぶ。ここで述べるのは現在の非上書き契約であり、任意の途中状態から自動再開できるという意味ではない。

段階138の検証は固定した模擬原本4件と有限の不正入力である。実受信機、全夜運用、実時計推定、低SNR画像尤度、GPU性能は未検証のまま残る。[段階レポート](../docs/reports/138-clock-input-contract.md)に正式な条件と結果を記録する。
