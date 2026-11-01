# 段階167：公開複数アンテナ電圧候補の出典と取得条件

- 作成日：2026-11-01
- 状態：調査完了。新しい複数アンテナ原本の取得・数値検証は未実施
- 比較元コミット：`aeeac2735da6a1a900653657c619f106921ce470`

## 読者向け概要

単局記録だけでは実基線を作れないため、複数アンテナの実電圧を取得する候補を調べた。小容量で公開されているファイルでも、試験用に作られた波形を実観測と扱うことはできない。MWA公式ライブラリのVCS試験例は変更済みメタデータと生成波形であり、実観測の代わりに採用しないと判断した。LWAにはCas A/Cyg Aを含む実TBNの一次論文があるが、対応原本の直接取得先・容量・利用条件までは確定していない。

## 1. 目的・対象範囲

次の実入力を選ぶ前に、具体的ID、実観測/模擬、個別アンテナ/ビーム合成、最小取得byte、取得条件を分ける。新しいreader/画像尤度/画像fitを実装しない。主な対象はMWATelescope/mwalib、LWA Software Library（LSL）、EPIC、MWA/LOFAR/LWAの公式案内。

GitHubの一次repo metadata・固定commit tree・説明コードと、公式archiveの読み取り専用検索結果を管理外に保存した。提供metadataそのものをGitへコピーせず、出典と取得判断の文章だけを公開する。

## 2. 完了条件

探索前の草稿に各HTTP2MiB/合計8MiB/timeout20秒、波形本体取得0、アカウント作成/job/連絡0を固定した。探索後の候補監査前に取得24fileのSHA、対象範囲、全Python431fileを固定した。候補ごとの採否を一次説明へ対応付け、未確認部分を成功扱いしない。匿名検索の空結果をデータ不存在の証拠にしない。新数値/回帰/MC/MCSE/GUI/相関/画像fitは対象外。

## 3. 実際に行った作業

| 候補・識別情報 | 確認できた根拠 | 今回の判断 |
| --- | --- | --- |
| mwalib `07f5e85724a5b1e45d54e5035b25810747627d4d`、`1101503312_vcs` / `1101503312_mwax_vcs` / `1370755832_mwax_vcs_os` | 各READMEは2 RF input＝1 tileに変更したmetafitsを説明する。電圧ファイルは試験時に生成する | 実観測の複数アンテナ原本として不採用。IDらしい名前だけで実観測と認定しない |
| MWA ASVOのVCS取得 | 公式案内は観測検索、API key、offset/duration指定の取得jobを説明する | 手続きと最小ファイルが未確定。本体取得/job投入なし |
| LSL `2a47cce0e421c239971f6a81d9403dcd94256b86`、`tests/data/tbx-test.dat` | 固定treeに40,960byteの試験ファイルが存在 | 元観測/対象/収録条件を未確認。小容量だけを理由に実天体入力へ採用しない。本体未取得 |
| LWA1 TBN、EPIC一次論文 | 255アンテナ・74.03MHz・100ksample/s・512sample/writeout・391writeoutの実データを記述する | 数値条件を候補として記録。対応する配布ファイルID/SHA/最小byte/利用条件は未確定 |
| LOFAR TBB | 公式案内はdipoleごとのraw電圧HDF5を説明し、LTA accountとstagingの取得手続きを示す | 公開metadataと匿名直接取得を区別。account作成/要求送信なし |

MWA試験例の根拠は固定commitの[README](https://github.com/MWATelescope/mwalib/blob/07f5e85724a5b1e45d54e5035b25810747627d4d/test_files/1101503312_vcs/README.md)と[生成を呼ぶtest code](https://github.com/MWATelescope/mwalib/blob/07f5e85724a5b1e45d54e5035b25810747627d4d/src/voltage_context/test.rs)。MWA実取得の案内は[公式Data Processing Documentation](https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24973422/Data%2BProcessing%2BDocumentation)。

LSL候補は[固定commitのtree](https://github.com/lwa-project/lsl/tree/2a47cce0e421c239971f6a81d9403dcd94256b86/tests/data)。LWA実TBN条件と天体画像の記述はThyagarajanらの[EPIC一次論文 §4.4](https://doi.org/10.1093/mnras/stx113)。論文中の処理結果をV-SoRAの成功へ継承しない。EPIC `c2bd68b792a5269cfffe1d93b4710eae9ba8ca55` の固定treeには対象波形を見つけていない。これは別の配布先の不存在を証明しない。

LOFARは[raw電圧の公式説明](https://science.astron.nl/telescopes/lofar/lofar-system-overview/observing-modes/direct-storage-mode-transient/)と[archive案内](https://science.astron.nl/telescopes/lofar/access-to-lofar-data/lofar-data-archive/)を参照。

## 4. 検証条件・結果

[LWA archive](https://lda10g.alliance.unm.edu/)の匿名read-only検索を確認した。LWA1/TBNで2011-09-21〜22、さらに表示可能な2010-01-01〜2026-11-01を検索したが、この匿名条件で表示される観測行は0だった。データが物理的に存在しない、認証後にもない、論文が再現不能という判断はしない。公開tutorialはDRX/画像の例と大容量ファイルの注意を示し、本体を取得していない。web表示工具での取得失敗と、直接HTTPSで取得できたHTMLを分けて保存した。

HTTP応答保存505,575byte、24fileをSHAで識別した。metadata/説明コード/検索HTMLは全て `outputs/stage167-preparation/discovery/` に保持し非公開。波形本体の追加取得0、既存CAMRAS再取得0、生成試験電圧0。新しい試験・MC・相関・画像計算を実行していない。[166](166-public-iq-samplebuffer.md)の数値結果は引用だけで再加算しない。

全Python431fileと既存入力SHAを保持した。監査対象の入力識別表・出典・判断・未確認事項は[検証案内](../../validation/runs/stage167/README.md)へ対応付ける。

公開監査指摘0、文書リンク2254件で欠落0。対象外tracked1558file SHA保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

新しい独立複数アンテナの実電圧をまだ取得していない。現在ローカルで由来を確認できる実rawはCAMRAS単局であり、実基線/Closure/Cas A画像の検証を増やせない。ライブラリのソフトウェアライセンスと、個別観測データの利用条件を同一と仮定しない。観測IDの形式や公開repo内の存在だけでも実観測と認定しない。

## 6. 次段階

取得可能な具体的ファイルと最小byte・出典・利用条件がそろう場合だけ、容量上限と検証目的を固定して取得する。account/job/連絡が必要なら必要性をユーザーへ提示する。単局参照の反復や、試験生成物の実観測への読み替えを避ける。別候補は166の16bit readerを製品化する際の時計/単位/offset/identity契約の検討であり、製品変更は両新全回帰/wheel/両実GUIを含む予算確保後に選ぶ。旧画像尤度・画像再fitは保留する。
