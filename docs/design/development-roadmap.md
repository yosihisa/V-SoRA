# V-SoRA：現在の開発計画

- 更新：段階160の文書整理、技術基準159（`ed067c8`）
- 最終目標：実RTL-SDR/OCXO、1.42GHz、最大基線約600m、局別周波数差、数百ms〜数秒、精密gain較正困難なClosure＋RML
- 最新の製品/full/wheel/両実GUI基準：151。最新の限定平均参照/対象試験：162
- 160以後の更新：161の有限3線/固定probe平均と162の同一電圧codec→整列平均を追記。全体文書の定期整理基準は159のまま
- 専用根本レビュー：150で実施済み、予定200。次の文書整理170。前提が崩れれば前倒し

## 判断の基準

実入力/取得環境の新回答を最優先する。148で一度照会しており、同じ質問を毎時繰り返さない。現Linuxから取得経路が見えなかった事実を、物理装置の不存在やWindows側不可へ変換しない。

[134契約](../../interfaces/image-statistics-contract.md)と[145の八条件](../../interfaces/image-noise-applicability.md)：前方平均、単位、共通標本集合、時間周波数依存、未知局量と推定、観測採否、joint Closure、目的関数を維持する。native RMLはw項あり、構築時固定の同種同cell共分散で、047JSON/044joint行列は読まない。共通集合とIID、047既定SNR5とproduction10、conditionalと内側有効行を区別する。

[150専用根本レビュー](../reports/150-fundamental-goal-review.md)で有限運用修正を前倒しし、科学側を一点ずつへ縮小した。160はその結果を現在計画へ同期する文書段階で、新しい根本レビューや数値計算ではない。実装・既知計算・有限模擬・実機未確認、完了・収束・適合・予測・形状を分ける。段階数/試験数を完成率へしない。

## 151〜162で完了した範囲

| 段階 | 実施した変更/参照 | 次へ自動継承しない条件 |
|---|---|---|
| [151](../reports/151-sequence-capacity-guard.md) | 既存128MiB式を共用し37/64窓を高コスト処理前拒否。両全2328/新wheel/両実GUI | 36窓完走、自動resume、全夜速度、画像品質 |
| [152](../reports/152-aligned-forward-mean.md) | 合成decoded reader・共有幾何の実整列API有限平均 | codec/量子化、実幾何精度、画像側広帯域平均/依存 |
| [153](../reports/153-quantized-finite-ensemble.md) | 別の固定8電圧集合を実codec/plain FXへ照合 | Gaussian/IID共分散、152との統合、実機補正率 |
| [154](../reports/154-archived-rate-gate.md) | 保存基線rate/powerへ採用maskだけを適用 | 局推定全体の純粋な偏りとgate因果効果の分離 |
| [155](../reports/155-image-covariance-gradient.md) | 供給receiverの画像依存C勾配/非一意性 | 未知局量、実低SNR Closure、production尤度採用 |
| [156](../reports/156-saved-closure-jacobian.md) | 固定priorの局所J/rank、直接FD未達とRichardson改訂 | 真Fisher/posterior、実画像誤差、物理gauge同定 |
| [157](../reports/157-smoothed-null-subspace.md) | 比較110arcsec全支持作用素と局所部分空間norm | 一次beam、power保持率、情報損失割合、confidence |
| [158](../reports/158-positive-null-candidates.md) | 保存方向の有限非負候補と非線形応答 | 許容振幅confidence、有限幅の厳密対称性、復元改善 |
| [159](../reports/159-point-channel-forward.md) | 固定合成幾何/decoded readerのtone空間位相・有限channel応答 | 実Astropy/codec、広帯域天空の周波数積分、実観測成功 |
| [160](../reports/160-documentation-checkpoint.md) | 技術基準159へ全体文書を同期、静的Git/JST/SHA照合 | 新しい数値/製品試験/専用根本レビューではない |
| [161](../reports/161-finite-band-forward-mean.md) | 同時混合3線/固定4符号の有限平均を実APIとmode別point応答和へ照合 | 連続PSD/Gaussian noise、codecとの統合、実観測成功 |
| [162](../reports/162-quantized-aligned-mean.md) | 同じ固定混合probeを実codec/FIR/補間/RF/FXへ通し独立復号波形の有限平均へ照合 | 実機較正、量子化後noise共分散/coverage、未知実観測成功 |

151の初回full優先順不備、153の独立float32参照、154の結果key、156のFD手順、157のprivacy誤検出、158の後処理field、159の観測grid不備、162のUTC文字列表現/保存診断field不備は各個別report/logに保持。修正前の成功を最終件数へ加算しない。131〜133の10画像/2不足、全10形状差prior超過は新参照で改善したとしない。

## 次の未選択候補163〜165

以下は実装済みでも実行予約でもない。実入力新回答、既存の重複、費用・期限で順序/範囲を改訂する。後段の前提が成立しなければ進めない。番号のため反復文書や小参照を増やさない。160当時の候補は[機械可読計画](../../validation/runs/stage160/next-candidates.json)。161/162はそれぞれの限定参照として完了し、現在の未選択は163以降。

### 163候補：推定と採用の識別可能な対照

前提：040/042/098/101/107/143/144/147/154をreviewし、新しい識別可能な差がある場合だけ。

目的：同pilotの推定依存と採用群の混在を、主経路へ適用する前に限定する。

受入：学習/評価への情報経路、事前固定支持と観測gateを区別し、graph不整合/失敗/null/採否indexを全保存。識別できない効果は未識別と判定。

予算：候補上限3局/64cell/1channel/512組、worker120秒、追加64MiB、公開512KiB。seed/MCSEは選択前固定。

中止/改訂：147/154の再集計だけなら追加しない。truthで探索/係数/実効M/weightを合わせず、採用群の差を無条件偏り除去としない。

### 164候補：具体的な確率モデルの独立照合

前提：八条件と前段の入力/平均/依存/未知局量/採否が具体化した場合だけ。現時点では保留。

目的：新しい画像尤度を採用する前に、何の密度かを定義して照合する。

受入：固定小入力の独立objective/勾配/正規化/不正値拒否を照合。既存100/155や044/047を単純加算せず、観測支持とモデル依存を明示。

予算：検証参照はworker120秒/追加64MiB/公開512KiB。製品変更は両full各900秒・両GUI各900秒・段階3600秒を初期上限として正式改訂。

中止/改訂：モデル未定なら実装しない。不足条件の反復文書だけを新段階にせず、未解決の入力/計算へ戻る。

### 165候補：固定入力での画像比較

前提：164相当のモデル接続が成立した場合だけ。現時点では保留。

目的：主画像経路への寄与を、処理完了/収束/適合/独立予測/形状に分けて評価する。

受入：原本・prior・格子・係数・失敗条件を実行前固定し、全run/不足を残す。未知真値をfitterへ渡さず、同raw/共有pilotと独立rawを区別。

予算：対象少数・各worker900秒/保存64MiB/公開512KiBを初期候補とし期限と残量に合わせ正式固定。

中止/改訂：条件未成立なら再fitしない。truthに係数を合わせず、外部RML追加反復/新GUIを自動で増やさない。

## 保留と運用

新production尤度/RML/画像再fit/GUI接続、外部RML追加反復、truthへ実効M/weight/画像係数/格子/seedを合わせる調整、Windows収録、全夜GPUは保留。実Cas A/未知実LO・gain・SEFD/beam/RFI/実FFT独立性/低SNR画像尤度は未検証である。

製品修正を選ぶ場合は新source/installed全回帰・wheel/pipcheck/全byte・checkout外API・両実GUIまで正式予算へ改訂する。GUI更新前は実所有/api/jobs idleを確認して所有idle GUIだけ停止し後に再開する。古いPTY/PIDを有効と仮定しない。

期限2026-11-06 15:00（Asia/Tokyo）、追加reset購入使用禁止。残量10%へ近づけば完成境界で休止し同じscheduleを期限前reset後へ調整、実回復を確認する。取得不能なら記録して大量の新段階を始めない。期限以降は新開発せず同一automationをPAUSEDにして報告する。次の文書整理170/予定根本レビュー200、前提崩れ時前倒し。[運用](development-governance.md)、[時系列](../reports/overviews/development-history.md)、[要素別進捗](../reports/overviews/goal-and-progress.md)、[短い案内](../guide/09-observation-readiness.md)、[索引](../reports/README.md)を参照する。
