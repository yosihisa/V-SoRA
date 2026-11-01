# V-SoRA：現在の開発計画

- 更新：170文書整理、技術基準169（`8317129`）
- 最終目標：実RTL-SDR/OCXO、1.42GHz、最大基線約600m、局別周波数差、数百ms〜数秒、精密gain較正困難なClosure＋RML
- 最新製品/full/wheel/専用両実GUI：169（両全2414/105file+4assets）。通常GUI151prefixは別に保持
- 160以後の更新：161の有限3線/固定probe平均と162の同一電圧codec→整列平均、163の局候補/χ²maskを追記。全体文書の定期整理基準は159のまま
- 専用根本レビュー150、予定200。次文書整理180。前提が崩れれば前倒し

## 判断の基準

実入力/取得環境の新回答を最優先する。148で一度照会しており、同じ質問を毎時繰り返さない。現Linuxから取得経路が見えなかった事実を、物理装置の不存在やWindows側不可へ変換しない。

[134契約](../../interfaces/image-statistics-contract.md)と[145の八条件](../../interfaces/image-noise-applicability.md)：前方平均、単位、共通標本集合、時間周波数依存、未知局量と推定、観測採否、joint Closure、目的関数を維持する。native RMLはw項あり、構築時固定の同種同cell共分散で、047JSON/044joint行列は読まない。共通集合とIID、047既定SNR5とproduction10、conditionalと内側有効行を区別する。

[150専用根本レビュー](../reports/150-fundamental-goal-review.md)で有限運用修正を前倒しし、科学側を一点ずつへ縮小した。160はその結果を現在計画へ同期する文書段階で、新しい根本レビューや数値計算ではない。実装・既知計算・有限模擬・実機未確認、完了・収束・適合・予測・形状を分ける。段階数/試験数を完成率へしない。

## 151〜163で完了した範囲

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
| [163](../reports/163-station-chisq-gate.md) | 保存基線を固定した現局LS候補と既定χ²mask、非連結nullを照合 | 全取得/探索/検出/graph選択と同pilot推定の因果分離、棄却profileの採用 |

151の初回full優先順不備、153の独立float32参照、154の結果key、156のFD手順、157のprivacy誤検出、158の後処理field、159の観測grid不備、162のUTC文字列表現/保存診断field不備は各個別report/logに保持。修正前の成功を最終件数へ加算しない。131〜133の10画像/2不足、全10形状差prior超過は新参照で改善したとしない。

## 2026-11-01：公開実I/Qによる優先順位の変更

ユーザー回答により受信機チームの実記録はなく、OCXO・構成・保存形式は未決定と確定した。148の照会は回答済み。その後、公開実I/Qを容量に注意してプロジェクト内へ取得・利用する指示があった。原本・提供metadata・派生波形/数値配列/図はGitへ載せず、取得配置手順と検証コード・方法/合否だけを公開する。

[164](../reports/164-public-single-station-iq.md)でCAMRASの単局かにパルサー原本16MBを取得し、全800万成分/有限FFTを両環境で照合した。供給Fs20MHzと小数秒capture epochを保持すると現VDIF入口の条件に合わない。単局で基線0のため相関/Closure/画像を実証していない。[取得配置案内](../guide/public-voltage-data.md)の32MiB取得上限/10GiB空きreserveを維持する。

[165](../reports/165-public-iq-vdif-time.md)で4000sample/frameの検証用VDIFへ供給20 MHz・小数秒epoch・全sample順を保持し、既存iteratorと独立量子化/有理数時刻を両環境照合した。製品writerの整数秒制約は維持。8bit化は非可逆で平均powerも変わり、production profileにしない。初回root検査不備は全終了後に修正し、全選択を再実行した。

[166](../reports/166-public-iq-samplebuffer.md)では原本16bit値を保持するreader prototypeを既存SampleBuffer境界に置き、実I/Qの固定4窓×seek/順次を独立有限作用へ照合した。入口での追加量子化は0だがFIR/補間は波形を変える。製品session/CLIへ形式を追加したものではなく、物理帯域/実時計の適用性は未検証。

次は複数アンテナ電圧の実観測ID・取得可能性・最小容量・利用条件を確認する候補。公称値の置換や単局複製で既存経路へ合わせず、同じ単局参照の小変更を自動反復しない。MWA本体取得/アカウント作成/取得ジョブ投入は未実施。製品reader変更を選ぶ前に単位/clock/identity契約と新両full/wheel/両実GUIを含め予算を改訂する。旧新画像尤度・画像再fit案は以下のとおり保留し、八条件が成立したと扱わない。

[167](../reports/167-public-voltage-provenance.md)でMWA公式の小容量VCS fixtureは生成試験電圧と判明し、実観測原本候補から除外した。LWA実TBNの一次論文は確認したが、直接配布file/SHA/最小容量/条件は未確定。匿名archive検索0件はデータ不存在の証拠にしない。次は具体的な新取得根拠がある場合の少量取得、または16bit reader製品契約を選ぶ。167はmetadata調査で新波形/相関/画像試験を追加していない。

[168](../reports/168-sigmf-reader-api.md)で限定ci16_le SigMF readerと単局SampleBuffer明示APIを製品へ接続した。両新全2392件、新wheel104file＋4assets全byte、checkout外API、両実GUI28条件を確認。追加量子化せず166固定窓の17配列へ一致した。新installedは独立prefix、通常GUI151の旧prefixは保持。session/相関CLI/InputIdentity接続、実clock/物理帯域guardは未実施。次は実複数アンテナ原本の具体的取得根拠を優先し、単局APIの小変更反復を自動計画しない。

[169](../reports/169-sigmf-identity-cli.md)でfresh metadata/data SHAのSigMFInputIdentityとinspect-sigmf CLIを接続した。期待値両指定/不一致と上書きを拒否し、両新全2414・105製品file+4assets/実CLI/API/両実GUI28条件を確認。全stat保持のraw変更は同instanceで見逃し得るため、閉じた入力と境界metadata rehash/別run fresh hashの契約を明示した。sessionへのSigMF形式接続やSampleBufferへの自動identity適用は未実施。次は170の文書整理を実施し、引用基準と次の具体的接続条件をそろえる。

## 旧候補164〜165：画像尤度・画像再fit案（引き続き保留）

以下は実装済みでも実行予約でもない。実入力新回答、既存の重複、費用・期限で順序/範囲を改訂する。後段の前提が成立しなければ進めない。番号のため反復文書や小参照を増やさない。160当時の候補は[機械可読計画](../../validation/runs/stage160/next-candidates.json)。161〜163はそれぞれの限定参照として完了。この旧画像尤度/画像再fit案は前提未成立で保留。164〜165という番号は上記公開I/Q検証に使用した。追加の局所参照を自動反復せず、実入力新回答や具体的モデル成立条件の更新を優先する。変化がなければ不足条件の反復文書を新段階にせず、必要に応じ根本レビューを前倒しして計画を改訂する。

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

## 170で同期した次の具体的接続候補

優先候補はSigMFのsession入口。既存VDIF/clock/identityを先にreviewし、形式、局ID、供給epochとclock modelのsample0/UTC、Fs/実rate、I/Q/scale、RF/帯域、原本pairの対応を実行前に固定する。metadataの公称値を未知の実clockへ代用しない。既存の相互に異なる模擬局電圧で旧VDIF数値不変とSigMF経路の独立照合を行い、公開CAMRAS単局は複数局不足として扱う。単局複製で実基線を作らない。製品変更なので両新full/wheel/pipcheck/全byte/checkout外API/両実GUI予算を再固定する。まだ実装/実行予約済みではない。

並行候補は実複数アンテナ原本の取得根拠。個別file URL/観測ID/実観測出典/最小byte/利用条件がそろってから目的・上限を固定する。生成fixtureを実観測へ変換せず、account/job/連絡を勝手にしない。新根拠がなければ同じ検索や不足文書を新段階にしない。

新画像尤度/再fit案は引き続き保留。未知局量/依存/採否/前方平均等の八条件を満たすまでは、100/155や044/047の単純加算を実装しない。段階番号で次作業を作らず、上記の具体的software接続と受入を選択して進める。

## 保留と運用

新production尤度/RML/画像再fit/GUI接続、外部RML追加反復、truthへ実効M/weight/画像係数/格子/seedを合わせる調整、Windows収録、全夜GPUは保留。実Cas A/未知実LO・gain・SEFD/beam/RFI/実FFT独立性/低SNR画像尤度は未検証である。

製品修正を選ぶ場合は新source/installed全回帰・wheel/pipcheck/全byte・checkout外API・両実GUIまで正式予算へ改訂する。GUI更新前は実所有/api/jobs idleを確認して所有idle GUIだけ停止し後に再開する。古いPTY/PIDを有効と仮定しない。

期限2026-11-06 15:00（Asia/Tokyo）、追加reset購入使用禁止。残量10%へ近づけば完成境界で休止し同じscheduleを期限前reset後へ調整、実回復を確認する。取得不能なら記録して大量の新段階を始めない。期限以降は新開発せず同一automationをPAUSEDにして報告する。次の文書整理180/予定根本レビュー200、前提崩れ時前倒し。[運用](development-governance.md)、[時系列](../reports/overviews/development-history.md)、[要素別進捗](../reports/overviews/goal-and-progress.md)、[短い案内](../guide/09-observation-readiness.md)、[索引](../reports/README.md)を参照する。

2026-11-01の最新指示で、今回に限り既存未使用resetの自動使用1回を許可された。新規購入と2回目の自動使用はしない。実残量10%以下で消費と回復を確認し、旧11月5日までの休止を解除して同一automationで継続する。上記期限は変更しない。過去の禁止・休止は当時の判断として残す。

その後ユーザーが手動resetを報告し、nativeで実回復・未使用数2→1を確認した。今回1回の承認は充足済みで、工具消費0回でも再使用しない。新weekly reset実値は11月8日20:30:03JSTで今回期限より後。毎回実値を優先し旧11月5日の予定へ戻さない。
