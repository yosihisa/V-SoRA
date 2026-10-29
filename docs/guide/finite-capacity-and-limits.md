# 固定VDIFの容量と、有限処理の制限

現行の小規模CPU参照を実行する前の、人向けの確認手順である。製品の新しいpreflightではない。[149の条件と実行記録](../reports/149-finite-capacity-limits.md)、[実入力の引渡し票](real-input-handoff-template.md)、[Linux入力確認表](../../interfaces/linux-input-readiness.md)と併用する。

## 原本のbyte数

次の式は、EDV0、8bitのIとQ、4096 complex sample/frame、32byte header、公称Fs2048000Hz、同じ長さの8局だけに適用する。別の保存形式やsample rateには、そのまま使わない。

- payloadは4096×2=8192byte、frame全体は8224byte。
- 1局のframe数は500/秒、byte数は4,112,000/秒。
- 8局では32,896,000byte/秒。これは保存形式から決まる計算値であり、ディスクや受信機の速度測定ではない。

| 名目時間 | 8局のVDIF bytes（header込み） | 根拠 |
| --- | ---: | --- |
| 3.04秒 | 100,003,840 | 4case×8局のstatと一致 |
| 1時間 | 118,425,600,000 | 固定profileの計算のみ |
| 8時間 | 947,404,800,000 | 同上 |
| 24時間 | 2,842,214,400,000 | 同上 |

4模擬caseのVDIF合計は400,015,360byte。表はVDIFだけで、元IQ、metadata、複製、相関出力、画像、失敗partialを加えた保存量ではない。metadataを別に保持し、元IQとVDIFの両方を残す場合は二重の保存が必要になる。既存[運用設計の4時間表](../design/2026-10-02-operational-architecture.md)も同じ固定profileの条件付き計算である。

131の`check_resources`にある512MiB生成予算・4GiB空きdisk・8GiB MemAvailableは、その有限模擬生成の開始条件である。一般的な必要PC仕様、実受信の連続取得速度、全夜処理の保証ではない。

## 上限は一つずつ確認する

| 段階 | 現行の条件 | 条件だけでは保証しないこと |
| --- | --- | --- |
| 整列相関1回 | integrations 1〜16384、span約3秒以下、基線×時間×周波数cell 100万以下 | raw長、時計精度、処理速度、画像に十分な信号 |
| Closure短区間 | pilot 8〜16384 cell、画像0.1〜3秒、FFT/frame grid、pilot被覆、rate探索のNyquist条件等 | 未知LO推定の成功、低SNR画像尤度 |
| sequenceの計画 | 2〜64窓、非重複、個々の有限条件、最終cell 100万以下 | 原本の末尾、最終RMLの行列上限、全窓の完走 |
| synthesis | 2〜64入力、軸/単位/位置/時刻/露出整合、重複拒否、100万cell以下 | 時間・周波数の独立性、RMLメモリ予算 |
| RML | pixels 8〜64、visibility数×pixels²×16が128MiB以下、採用Closure等 | プロセス全体のpeakRSS、科学的妥当性、収束、GPU性能 |

MiBは2²⁰byte。RMLの式は複素128bitの直接Fourier行列だけを見積もる。入力、Closure共分散、最適化中の一時配列等は別にあるため、この値を搭載RAMやpeakRSSと読まない。

### 8局・8チャネル・32画素では64窓を完走できるとは限らない

1窓1時間cell、基線28本を保つと、行列は1窓につき8×28×32²×16=3,670,016byte（3.5MiB）になる。現行`process_sequence`はsynthesisへ**pixels=32を固定で渡す**。時間・チャネルをまとめて複素平均したり、無効行を削ってから行列を作る経路ではない。

| 窓数 | 32画素の行列 | 現行行列上限との比較 |
| --- | ---: | --- |
| 36 | 126MiB | この上限だけは満たす。完走は未確認 |
| 37 | 129.5MiB | 超過。既存RML APIで早期拒否を確認 |
| 64 | 224MiB | 計算上超過 |

149で36/37/64窓の`plan_windows`はすべて受理されたが、37窓の`ClosureObjective`は行列生成前に拒否した。原本・相関値・画像を新しく作って全系列を通した結果ではない。131と同じ軸寸法を使った計画例で、3.04秒の131原本を36窓へ増やしたものでもない。

低水準RMLへ16画素で64窓を渡した場合の行列は計算上56MiBだが、sequenceにはその画素数指定がない。この計算例を回避手順や画像品質の保証にしない。画素数やcell数を変える場合は、必要な視野・分解能・統計条件と製品の正式検証を別途定める。

窓間のstepを長くすれば、選択区間の最初から最後までの時間は長くできる。一方、各pilotは3秒以下、窓は64以下で、連続全夜を自動分割して処理する機能とは異なる。空白の時間を積分済み露出へ加えない。

## 失敗後の扱いと、未測定の量

上位Closure pipeline/sequenceのInputIdentityはrunごとに原本の全byte hashを作り、stat境界とmetadata再hashを扱う。同じ原本・設定・clock・rate profileを識別して保持する。hash一致は物理時計や全headerの証明ではなく、直接`correlate_aligned`だけで同じ上位管理が働くとも限らない。

[139](../reports/139-finite-operation-recovery.md)は末尾不足でpartialを残し、同じ出力先を拒否し、正しい区間を別出力で処理することを確認した。任意checkpointからの自動再開ではない。sequenceの窓処理/合成の失敗段階は既存状態記録で区別するが、149では失敗後の系列再処理を新しく実行していない。

139の4ms出力16,658byteは圧縮やmetadataを含む一例で、長時間の出力容量へ比例外挿しない。単発wall時間・生涯peakRSSにもhash/import等が含まれ、取得throughputや全夜処理時間へ外挿しない。実運用では、取得速度、drop、原本保持、partial容量、反復実行、連続性、時計・gain・RFIの有効区間を実入力で測る必要が残る。

150の文書整理・専用根本レビューで、この制限の組合せを次の優先順位へ反映する。早期の一括判定や全夜driverを実装済みとはしていない。
