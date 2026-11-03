# 段階182：明示clockモデルによるLBA複素帯域query

- 作成日：2026-11-04
- 状態：完了
- 比較元コミット：`17ac7796bea70a4fcb0dc17240f8bf0e0515b037`（181）

## 読者向け概要

181の出力は「何番目のsampleか」を保つが、局ごとの実clockを測定するものではない。今回は、callerが明示した時計と周波数原点を使い、指定時刻の有限補間値を得るAPIを追加する。局別のsample rateに依存するmixer位相と、補間に必要な前後sampleを対応付ける。実録音の未知clockを公称値で埋めず、人工入力で算術を検証する。[契約](../../interfaces/lba-clocked-band.md)、[手順](../../validation/runs/stage182/README.md)を公開する。

## 1. 目的・対象範囲

新 `vsora_correlator.lba_alignment.LBAClockedBandView` で、live181viewと既存 `clock.interpolate_samples` を接続する。元reader/codec/identityを再実装せず、元sample indexと中心FIRを保つ。局ID/偏波/epoch/actual rate/RF/phase offset/宣言provenanceを記録し、FIRと補間のnested support、caller invalid区間、位相原点を扱う。

時刻・周波数はcallerモデルであり推定・認証ではない。session/600m guard/VDIF/SigMF/既存LO profile/RML/Closure/画像を変更しない。旧107製品sourceを保持し、製品moduleを1追加する。

## 2. 完了条件

実装前に目的/具体API/入力生成式とSHA/許容/MCSE有無/全失敗保持/時間byteを固定した。nativeは00:05:27JSTに100%/週間10%への実回復を確認した。最新ユーザーが今回1枠に限り週間reserve使用を許可し、5時間10%reserveと追加reset購入使用禁止を維持した。対象は11月4日00:05頃〜05:05:16 JSTで、遅れても終了を延ばさない。

model全10key、UTC-Z最大9桁label、actual rate±1000ppm、相対offset/query絶対3秒以内、query1〜2048点、読込中心最大16384。中心FIRとradius32補間を元座標で結合し、別causal filterや群遅延補償は加えない。RF中心差はR/16以下、cycleの式は契約へ固定。未知値/数値bool/非有限/範囲外/support不足/モデル変更を拒否する。

人工fixtureの12caseを独立scalar decode/129項FIR/65項補間/位相の有限参照へRTOL1e-9/ATOL1e-5 code-unit。Fractionでexact binary inputの座標へATOL1e-9sample。whole/分割[1,7,31,90]を厳密一致。source/installedの60NPZ fieldと科学JSONは全一致し、時間/RSS4fieldだけを比較から除外する。MCSEなし。実4局はunknown actual clock/RFでquery前に拒否する。

両新source/installed対象/collect/full、新wheel/pipcheck/108製品+4assets全byte/module origin/依存版、checkout外helper不要API・実workflow CLI・既存CAMRAS inspect-sigmf実CLI、両実Chromium各28保存診断条件を選択。旧prefixと179初回archiveを保持する。

worker120秒、study追加peak256MiB/保存各64MiB、full/GUI900秒、attempt3600秒/全7200秒。全attempt/pytest一時/新prefix/補助/管理記録/公開textを含む4GiB/空き10GiB reserve/公開512KiB。正式中source/tests/tools/workflows/helpers/入力固定、修正は全worker終了後だけ。失敗log/部分/freezeを保持して全選択を再実行し、初回成功を合算しない。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/lba_alignment.py`：明示callerモデル、source guard、有限補間、RF原点のphase、invalid support伝播。
- `apps/correlator/tests/test_lba_clocked_band.py`：有限参照/分割/境界/未知値/型/親変更/単位変更/query中guard/extra guardの検査。
- `workflows/lba_clocked_band_validation.py`：固定人工fixtureの独立有限和と、実原本の未知clock/RF拒否のstudy。
- interface/公開電圧案内/roadmap/report索引/本report/text validationを更新。

親のnominal epochをmodel epochへ自動転用せず、指定epochからの相対秒だけでqueryする。provenanceのmeasuredという文字列もcaller主張であり、APIが実測を確認した意味ではない。数値unitはcode-unitを保持する。新parent full hashやpersistent cacheは作らない。

## 4. 検証条件・結果

新人工fixtureはheader16byteとpayload8192byte、byte i=(73*i+19)%256、offset1/R,L/供給8MHz/16384 time sample。実天体観測や新Monte Carlo標本ではない。fixture SHAは準備記録に固定し、原本/配列/科学JSONは管理外へ置く。

actual rateの試験モデルは8000083/7999873Hz、offset .001/.0027秒、RF端1719000137/1718999789Hz、共通RF中心1721000000Hz、phase .2/−.4rad。各2偏波×start96.125/1027.25/12000.5、129query/step1.0001sample、invalid raw区間[1050,1052)で計12case。これらを実LBAのclock/RFへ注入しない。

事前初回対象120成功の後、study1がwhole/1点分割の3.637978807091713e-12 code-unit差を検出して停止した。全worker終了後、phase計算を長さ依存SIMD経路からscalar libm/complex演算へ揃え、許容・入力・有限式は変えず全選択を再実行した。study2成功後に単位context guardと誤解しないmetadata名を追加し、事前最終121成功/新study成功。旧product/test/log/部分出力を保持し、初回の成功を合算しない。

事前最終studyは60field、独立最大差5.800474011324368e-8 code-unit/座標差0、invalid出力484、約0.142秒/追加peak1916928byte。同じ固定有限operatorの代数検査であり、実時計精度/FFT独立性/noise尤度の校正ではない。

正式初回はinstalled studyの公開helper import経路不足（ModuleNotFoundError: workflows）で停止。source全回帰2694成功などの初回成功を合算しない。installed studyはimport時に停止し数値study0。所有11workerの全終了をhost確認後、全log/出力/freeze/wheel/prefix/helpers/旧workflowを `outputs/stage182-formal-attempt1` へ保持した。成功pytest一時878015089byteだけを所有・lock不在・正式時刻内で確認して削除した。

訂正は公開workflowの直接CLI実行時に、公開helper参照用のrepository rootだけをsys.pathへ加えるもの。製品/入力/数値許容は不変。installed製品moduleは全て新prefixから読むことを検査し、helper不要APIは別probeで確認した。全選択をattempt2へ再凍結・再実行して成功した。初回7238file全SHAと凍結codeの再構成を最終静的照合した。

最終attempt2は両対象273成功/2857既存種別warning、collect/full各2694成功/39404既存種別warning/除外0。source627.97秒、installed629.15秒。19worker全終了、非上書き2return1は意図した拒否で既存出力SHAは保持した。全60NPZ field/科学JSON/checkout外API JSONはsource/installed厳密一致。

新wheel `ec2e48c3a3b90286bc1c350f89157df7e7fe515606cf054e413722acf5fa2309`、108製品+4assets全byte、6study module origin/byte、44依存版/pipcheck、checkout外helper不要API/実workflow CLI/既存CAMRAS inspect-sigmf実CLIを確認。旧107製品source、旧151/168/169/171/172/173/174/175/176/177/179/181 prefix、179初回archiveを各旧wheel byteへ照合。新installed基準は `outputs/stage182-installed-venv`。

両実Chromium各28条件/56JSON/672行/JavaScript error0/外部要求0/日本語390px。保存模擬診断回帰で新LBA/SigMF画面ではない。helper固定stage137/production_changed:falseは182製品未変更を意味しない。通常GUI151の更新・再起動0。

両studyの独立最大差は5.800474011324368e-8 code-unit、exact binary座標との差0、invalid出力各484で固定許容内。source study約0.151秒/追加peak2027520byte/保存85898byte、installed約0.146秒/2072576byte/86140byte。同じ人工有限標本の再実行で、実観測試行/実FFT独立性/実clock測定ではない。実4局は未知clock/RFのためquery前拒否、実原本complex query0。親constructorの原本SHA検査や全入力再照合のI/Oと、変換・実機throughputを混同しない。

凍結1291file/465Python/固定入力320SHA、131原本76SHA/CAMRAS3SHA/LBA14fileと過去参照を保持。最終正式1287.10秒、初回開始から訂正待機を含む最終正式終了までの保守的経過は2122.38秒で全7200秒内。両attempt/pytest一時を含むworker境界最大2873626099byte。管理記録全体/公開text/残りtext4MiB reserveを含む保守上限2879904899byteで4GiB内。全終了・所有・lock不在・正式時刻内を確認して成功pytest一時1653996618byteのみ削除、全失敗証跡と初回archiveは保持。削除後の全182保存1219670746byte/空き38573465600byte（集計時点）。連続filesystem peak測定ではない。

公開監査指摘0、文書リンク2446件で欠落0。9fileのstrict allowlistで公開し、対象外tracked1621fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

モデルのstation/clock/RF/phase/provenance/invalid区間はcallerの宣言であり認証・gap/RFI検出ではない。有限FIRの鏡像/応答と有限補間を残し、一般anti-aliasや理想解析信号としない。sourceのunknown actual clock/局ID/RFは変更せず、実録音への未知値注入で整列を合格にしない。

178実4局（6組合せ）を得た事実と、検証済み実相関基線0を区別する。今回新しい実原本complex query/実相関/Closure/画像study/MCは0。既存full内の模擬画像試験と区別し、131原本再生成/再相関/再fitは行わない。原本/提供metadata/派生科学JSON・配列・図のGit公開0。

閉じた入力/trusted Pythonを前提とし、全stat保持raw変更/最終guard後の変更/file lock不在の限界を継承する。fragment SHAを未取得member/archive全体SHAやproducer認証としない。実Cas A/RTL-SDR/OCXO/未知LO gain SEFD/beam RFI/低SNR画像尤度/全夜GPUは未検証。

## 6. 次段階

今回の許可は1枠だけで05:05:16 JSTに終了する。予算と終了条件に従って完了境界を優先し、同じautomationを停止して結果を報告する。追加resetは使わない。将来実相関を選ぶ場合は実clock/RF/geometry/単位の供給と、600m主経路と長基線参照の別契約が必要。形式接続から新noise/RML尤度や実画像精度を導かない。文書整理190/予定根本200、専用根本レビュー150を継承する。
