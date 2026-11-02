# 段階175：SigMF補正窓の結合契約

- 作成日：2026-11-02
- 状態：完了
- 比較元コミット：`41c361801148507f0fb4709a79aeb3520ec841c9`（174）

## 読者向け概要

174の保存済み窓を後段へ渡す前に、時刻と元入力の対応を保つ。既存mergerはUTC原点を小数秒3桁で保存し、元のmetadata/data pairの識別を直接引き継いでいなかった。またvalid_fft_countを結合対象へ含めていなかった。今回はSigMFだけを対象にこれらを保持し、画像fitを行わない明示入口を追加する。原本識別の一致は保存された情報の照合であり、実原本や実時計を再検証するものではない。

## 1. 目的・対象範囲

SigMF spectral入力のUTC9桁、保存pair/clock/観測config識別、全数値fieldを保つ。API `merge_spectral` と `vsora-synthesis --merge-only` で、画像fitや複素平均を行わず補正窓を結合する。Closure/RMLのnoise model・covariance・weight・mask・目的関数は変更しない。新画像尤度の八条件が成立したとはしない。session-levelのSigMF画像pipeline/画像sequence/GUIは引き続き拒否する。

## 2. 完了条件

目的・入力SHA・固定許容/失敗・時間byteを実装前に管理外へ固定。全入力SigMF/ADC²、同じ局順ID/pair/clock/観測config/UTCを要求。SHA・byteの型、欠落/混在/原本差/既merge/重複/overlap等を拒否し、既存出力を上書きしない。元原本を再openしていないことを結果へ明示する。legacyの全field/metadata/returnを旧174対照へ厳密一致、新SigMFの全数値を独立concat/sortへ厳密一致させる。新両target/collect/full/wheel/pipcheck/全byte/checkout外API・実CLI/両実GUIを選択し、公開監査/commit/push/実remote一致・cleanで完了。

## 3. 実際に行った作業

`synthesis.py` に保存SigMF identityの一致検査と9桁UTC serialization、valid_fft_count保持、未知の非diagnostic field拒否、merge-only CLIを追加。既存legacyの結合と既定画像CLIは維持する。`test_synthesis.py` に独立整数ns、欠落・型・pair/clock/obs/epoch差・mixed・count/未知field・再merge・CLI非fitの試験を追加。`sigmf_merge_validation.py` は保存174の窓を逆順で入力して照合する。[契約](../../interfaces/sigmf-spectral-merge.md)を参照。

共通identityのserialized key順は固定し、process間でmetadata_jsonの並びが変わらないよう正式前に整理した。事前reviewで見つけたcountの引継ぎ不足はpurposeへ追記し、SigMFだけを変更した。RML/Closure・原本・推定profileは変更しない。

## 4. 検証条件・結果

174 source-studyのSigMF/legacy各2完成correlation shardを全SHA固定して再利用。保存038の異なる模擬4局由来で、供給nominal clock・固定code-unit尺度のまま。rawの再生成/再相関/変換/新取得0、131原本の再処理0。新MC study/新画像study fit0で、既存全回帰の画像試験とは分ける。

元2窓の全数値を独立にconcat/sortし、新SigMFの13数値field・legacyの12数値fieldを厳密一致。legacyだけは従来どおりvalid_fft_countを含めない。SigMFは新たにこのfieldを保持する。旧174 installed mergerでlegacy対照を保存し、新legacy NPZのschema/metadataを含む全fieldとreturn JSONを厳密一致させる。174の独立電圧作用の合格を今回の新試験数へ加算しない。

小数秒部分の試験は人工metadataのunit fixtureだけで行う。UTC .123456789Zとoffsetからの絶対時刻をPython datetimeと整数nanosecondで別計算し1ns以内、3桁丸めの負対照差456789nsを確認する。元raw/提供metadataのepochやFsを加工して既存profileへ合わせない。これは供給値の算術・serialization試験で実時計の精度測定ではない。MCSE適用なし。

事前対象22成功の後、count/未知field試験を追加し最終27成功（0.34秒）。事前study初回成功。正式初回の全選択が成功。事前22件と27件を足し合わせず、最終の選択結果を示す。

| 環境 | 対象成功 | full成功 / collect | full pytest時間 | 既存種別warning |
| --- | --- | --- | --- | --- |
| source | 96 | 2496 / 2496 | 578.81秒 | 37652 |
| installed | 96 | 2496 / 2496 | 576.75秒 | 37652 |

除外/skip0、全worker終了。SigMF13/legacy12数値fieldは元窓への独立concat/sortと厳密一致。新source/installedではschema/metadataを含むSigMF15+legacy14=計29fieldと各return JSONを全て厳密一致。旧174 legacyもNPZ全14field/metadata/return一致。原本rawの再hash/再相関や電圧変換はproduct merge studyでは行っていない。

新wheel SHA256は `aa4803edfd4149d174ca898962c0bf4614088077e9c8062835f16d09a0706473`。105製品+4assetsのsource/wheel/installed全byte、4study moduleのorigin/byte、pipcheck、44依存版一致、checkout外helper不要API、両実CLIのNPZ/JSON一致が成功。非上書き4件の非zeroは意図した拒否で、既存出力SHAを保持した。旧151/168/169/171/172/173/174 prefixは各旧wheel全byteと一致。

両実Chromiumは各28条件/56JSON/672行/JS0/外部0/日本語390px。保存模擬診断のGUI回帰であり、新SigMF画面ではない。通常GUI151を更新/再起動しない。study/APIではRML/Closure moduleがimportされていないことを確認した。

凍結1278file/451Python、固定入力208file、131原本76SHA、CAMRAS3SHAと旧原本/参照を保持。追加peakはsource 14532608byte / installed 49426432byteで256MiB内。study全保存は200102byteで64MiB内。正式後の全追加保存集計609418874byte、空き41855733760byteで2GiB/10GiB reserve内。取得/変換/実基線/新MC study/新画像study fit0。原本・metadata・派生数値の公開0byte。

[text validation](../../validation/runs/stage175/README.md)に方法を記載。原本・提供metadata・科学JSON/NPZ/図・log/freezeは全て管理外。

公開監査指摘0、文書リンク2348件で欠落0。10fileのstrict allowlistで公開し、対象外tracked1589fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

保存identityの一致であり、原本やproducer checksumの再認証ではない。fresh hashは閉じたspectral fileを対象とし、元rawの現在状態、正しい形の偽metadata、敵対的filesystemやfile lockを証明しない。原本へのfresh検査は上流171〜174と区別する。countを独立FFT標本数/実効Mやconfidenceへ読み替えない。legacy側の既存field構造は保持した。

実基線0、実Cas A/未知実LO・gain・SEFD/beamRFI/実FFT独立性/低SNR画像尤度/全夜GPUは未検証。八条件、native RMLのw項/固定同種同cell共分散/047JSONと044jointを読まない条件は不変。精密gainや絶対fluxを相対画像へ一律必須としない。通常GUI151を更新/再起動しない。専用GUIは保存模擬診断の回帰で新SigMF画面の検証ではなく、helper固定stage137/production_changed:falseを今回の製品未変更と解釈しない。

## 6. 次段階

session-levelの画像入口を選ぶ前に、局/時計/単位/原本と保存識別の対応、既存高SNR近似の適用範囲、時間周波数依存と画像入力の具体的受入をreviewする。新モデルや新画像fitは独立受入/正式予算を先に固定する。既存部品を重複実装せず、番号のためのcodec反復や不足文書を増やさない。文書整理180/予定根本200。
