# 段階151：系列のRML容量を高コスト処理前に検査する

- 作成日：2026-10-29
- 状態：完了（有限運用の製品修正。画像雑音モデルの変更ではない）
- 比較元コミット：68e8717be5b985c994cfdb83cc83f9f26141cf3e（150）

## 読者向け概要

系列処理は、いくつかの短い相関を保存し、それらを画像化へまとめる。149では計画上64窓まで選べても、最後の画像化で必要になる行列が大きすぎて拒否される条件が見つかった。全窓の相関を終えた後に初めて分かる拒否を避けるため、同じ容量式を計画の前段でも使うようにした。

8局・8チャネル・32画素では、36窓の行列は126MiB、37窓は129.5MiBで、上限は128MiBである。修正後は37/64窓を原本全byte hash・相関worker・buffer・partial作成前に拒否する。36窓はこの容量条件を満たすだけで、原本の長さ、信号の強さ、全系列の完走まで保証しない。

## 1. 目的・対象範囲と完了条件

150で前倒しした有限運用修正である。RMLの既存行列上限をprivate helperで共用し、sequenceの最終保存cell数と固定pixels32で同じ検査を行う。新しい公開preflight製品、画素数指定、尤度、weight/実効M/正則化係数は追加しない。既存の入力・三次統計保存・非上書きのエラー優先順を保持する。

新unit/target/collect、source+installed新全回帰、wheel/pipcheck/package全byte+4asset、checkout外API/実CLI、両実GUI28条件を完了条件とした。有効な固定3窓系列の全NPZ配列とmetadata・画像NPY・時間だけを除くJSONが、修正前の対照と完全一致することを要求した。

各全回帰/GUI900秒、段階3600秒、独自系列出力は各16MiB・合計64MiB、公開記録512KiB以下を正式選択前に固定した。既存3窓の圧縮NPZ約7.12MBを確認したため、草稿の16MiBを全run合計とせず、複数の対照を含む予算へ具体化した。開始時空き約48GBを確認し、追加resetは購入使用していない。

## 2. 修正前に確認したこと

131 high_aの実manifestを読み、8局/FFT8/1024block・pilot750 cell・画像0.3秒・start0.002秒で36/37/64窓の既存計画を実行した。すべて受理された一方、shape(37,8,28)を渡したRML単体は128MiB超過で拒否した。raw全系列を処理した反例ではなく、既存計画と既存RMLの小入力の差である。

有効対照は、既存032の4局・800frame原本を再生成せず、3窓/step0.512秒/画像0.3秒/starts1/最大100反復で実行した。初回の準備runはBLAS thread数が未指定だったため、log/出力を残すが正式比較元へ使わない。比較元150のrml/sequence定義を別プロセス内でGitから読み、他の不変sourceを共用してBLAS1/OMP1でcontrolled baselineを取得した。workspaceのsourceを旧版へ戻していない。正式後も同じthread設定で比較した。

## 3. 実装と検査順

容量は`visibility_count × pixels² × 16byte`で計算する。複素128bitの直接Fourier行列だけの見積もりであり、peakRSSや必要な搭載RAMではない。RML単体は元と同じgeometry検査の後に同じ上限を確認する。重み0/無効行で行列の保存cell数を過小にしない。

- `vsora_imaging.rml._validate_fourier_size`へ元の上限式と拒否文を移し、RML単体と系列で共用した。
- 系列の固定画素数32をprivate定数へまとめ、容量予測と実際のsynthesis呼出に同じ値を使う。新しい画素指定はない。
- 元の純粋な計画をprivateに分けた。公開`plan_windows`はその計画と容量を検査する。`process_sequence`は元の計画、指定時の三次統計寸法、出力先/partialの非上書きを検査してから、容量を確認する。その後に初めてpartialとInputIdentityを作る。

容量が通っても、raw末尾、clock、rate取得、Closure不足、画像収束等の後段は独立に失敗し得る。既存上限を緩めず、全条件の一括認定にもしていない。

## 4. 初回全回帰の失敗と、終了後の訂正

最初の実装は容量検査を公開計画に追加し、source22対象とAPI・28 GUIを通った。しかし全2326回帰では、任意raw bispectrum保存の非対応寸法エラーを新guardが隠し、**1失敗・2325成功・30220警告、555.20秒**となった。失敗は既存`test_unsupported_storage_dimensions_rejected_before_pipeline_output[sequence]`である。

全回帰・ブラウザ・buildがすべて終了した後だけにコードを変更した。従来のbispectrumエラーと非上書きエラーを先に返す上記の構成へ整理し、既存出力先/partialの優先順2試験を追加した。新unitは計7件。再凍結後、全対象・collect・全回帰・wheel・API・GUIを再実行した。初回の2325成功、22対象、GUI成功は最終の正式件数へ合算していない。初回log、初回wheel、初回凍結manifestをGit管理外に保持し、失敗要点を[正式記録](../../validation/runs/stage151/verification.json)へ残した。

## 5. 検証条件・結果

### 型・順序・高コスト処理への未到達

新7試験は36窓の容量条件、元の重複エラー優先、37/64窓のInputIdentity/worker/buffer未到達、既存出力先/partial優先、RML単体の重み0/1での容量拒否を確認する。既存の三次統計保存試験も対象へ加えた。実manifestのAPIとcheckout外CLIでも、clockファイルが存在しない条件で先に128MiBエラーとなり、出力/partialを作らないことを確認した。

| 最終の新実行 | source | installed |
| --- | --- | --- |
| 対象回帰 | 43成功 / 57.74秒 / 6569警告 | 43成功 / 57.3秒 / 6569警告 |
| 実collect | 2328 | 2328 |
| 全回帰 | 2328成功 / 552.61秒 / 30220警告 | 2328成功 / 551.31秒 / 30220警告 |
| 除外 | 0 | 0 |

警告は既存のBaseband/NumPy等の非推奨警告として保存し、除外していない。正式検証中のsource/tests/tools/workflowは451項目のSHAで固定した。

### 有効系列の数値保持と導入経路

source API、導入API、導入の実CLIの有効3系列をcontrolled baselineへ照合した。各8 NPZの120フィールド（metadataを含む）、34 JSON、画像NPYが一致した。JSONはoptimizerの実測`elapsed_s`だけを比較から除き、sample時刻や露出は除いていない。source/導入APIは各30製品moduleの正確なsource位置/導入prefixを確認した。導入はcheckout外cwd、runner/PYTHONPATHなしで、CLIも同じ導入Pythonの新プロセスを使った。API/CLIの完成先再実行は非上書き拒否となった。[参照と比較](../../validation/runs/stage151/reference.json)に全結果を保存した。

新wheelは103 package fileと4参照assetについてsource/wheel/installedの全byteを照合した。138 wheelから変わる製品fileはsequence.pyとrml.pyだけ。pipcheck成功、実行時依存版はfreezeで不変。wheel SHA-256は`c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec`。

### 実ブラウザと通常GUI

既存の保存診断28条件を、source/導入の実Chromium 153.0.8010.12で操作した。各28 worker/56 JSON download、672基線行、null50/負174/1超148、局ラベル/SNR/Closure誤差/全JSONが既存記録と一致した。各10moduleの位置、日本語font/390px、ページoverflowなし、表の折り返し、JSエラー0/外部通信0を確認した。横scrollを検証したとはしない。これは既存保存診断の回帰で、新しい画像診断ではない。

通常8765は実所有PID/args/cwd/uidと実api/jobs idleを改めて確認し、所有idle GUIだけ停止してwheelを更新した。旧PTYを有効と仮定せず、新しい所有プロセスで再開しHTTP200/activejobs0を確認した。専用ブラウザ回帰serverと通常GUIは別である。

## 6. 変更ファイル・保持と公開

製品2fileと試験2file、本report/索引、[有限容量案内](../guide/finite-capacity-and-limits.md)、[系列規約](../../interfaces/closure-pipeline.md)、[計画の151完了追記](../design/development-roadmap.md)、[小容量記録4件](../../validation/runs/stage151/README.md)の13ファイルを公開対象とした。対象外tracked1468と凍結451中の未変更447項目は不変。131原本76SHA、032入力11SHA、保存相関12/pilot12/profile4のSHAを保持した。

[実行計測](../../validation/runs/stage151/measurements.json)と[正式検証](../../validation/runs/stage151/verification.json)で最終実行・初回失敗・引用を区別する。公開監査指摘0、文書リンク2054件で欠落0。

主比較で原本を新生成していない。準備/正式比較では有限のRML系列を再実行し、全回帰では既存試験が一時模擬VDIF/相関/画像を生成した。新しい科学画像比較や低SNR較正とは分ける。古い138全回帰を新成功として引用するのではなく、今回は両2328を新実行した。

## 7. 制約と次段階

この変更は高コスト処理の後に分かっていた容量拒否を前へ移すもので、画像の形、感度、低SNR尤度、未知の実LO/gain/SEFD、実時計/beam/RFI、実FFT独立性、全夜/GPUを検証した結果ではない。36窓の全系列は実行しておらず、行列容量だけの受理を成功へ変換しない。

150の専用根本レビューは完了済みで、繰り返していない。次152候補は、既存参照をreviewして実整列query・幾何RF-rate位相を含む前方平均の未接続差を一点だけ選ぶ。量子化/未知推定/選別を一度に変えず、同等対照が既存なら重複しない。新RML雑音接続/画像/GUI、外部追加反復、truth調整、Windows収録は保留。次の文書整理160、予定の専用根本レビュー200、前提が崩れれば前倒しする。

継続期限2026-11-06 15:00（Asia/Tokyo）、追加reset禁止を維持する。段階数/試験数は完成率ではない。
