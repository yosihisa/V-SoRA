# 段階181：偏波別LBA複素帯域view

- 作成日：2026-11-03
- 状態：完了
- 比較元コミット：`c8e1d26571d3c5213dc405d7d6730a40c9b61909`（180、製品基準179）

## 読者向け概要

LBAの2つの偏波は別の実数信号で、IとQの組ではない。今回、1つの偏波を選び、その実数信号を固定の複素振動と有限filterで処理する明示APIを追加した。必要な帯域の複素表現へ進むための処理で、実clockや物理電圧を測定する機能ではない。[契約](../../interfaces/lba-complex-band.md)と[手順](../../validation/runs/stage181/README.md)を公開する。

## 1. 目的・対象範囲

179のlive `LBAFragmentRecording` を再利用する `LBAComplexBandView` を追加する。元reader/codec/identityを重複実装せず、各偏波を個別に扱う。供給USBのquarter-band mixing、129tapの中心FIR、元sample indexと両端supportを固定する。downsampleや元epoch/Fsの変更、R/LのI/Q化は行わない。

actual_rate/局ID/RFは未知として保持し、既存physical-time SampleBuffer/session/相関/GUIへ自動接続しない。実相関の600m制限・明示clock・単位契約を緩和しない。新noise/RML/Closure/画像の成立を主張する段階ではない。

## 2. 完了条件

実装前に目的/契約/入力SHA/固定許容/時間byte/全失敗保持を管理外へ固定した。NCOは元source sample index mod4で位相を保持、factor2/129tap Kaiser beta8.6/cutoff7/32cycle per sample/DC gain1で固定する。両側64supportを要求し、外挿・paddingで測定済みsampleを作らない。

独立sinc/Kaiser式の係数へRTOL1e-13/ATOL5e-15、固定7点のpass gain誤差と鏡像gain各1e-3以内。合成decoded toneの14条件を、desired+mirror両項の有限operator予測へRTOL1e-11/ATOL1e-8 code-unitで照合する。これは連続帯域のsup保証や実受信試行ではない。

178の固定原本/保存levelsを再利用し、8偏波の全有効16776192 complex sampleをchunk4096/16384でそれぞれ一巡してstream SHA一致を要求。48固定窓を独立有限和へ同じ許容で照合し、source/installed全53NPZ field/方法JSONを厳密一致させる。時間/RSS4fieldだけを比較から除外する。MCSEなし。

新source/installed両対象/collect/full、wheel/pipcheck/107製品+4assets全byte、module origin/依存版、checkout外helper不要API・実CLI、両実Chromium28保存診断条件を正式選択する。旧106製品sourceと全旧prefix byteを保持する。新画面ではなく通常GUI151を更新・再起動しない。

worker120秒/追加peak256MiB/科学保存各64MiB、full/GUI900秒、attempt3600秒/全7200秒、全attemptとpytest一時出力を含む4GiB/空き10GiB reserve/公開512KiB。正式中source/tests/tools/workflows/helpers/入力固定、修正は全worker終了後だけ。失敗log/部分出力/freezeを保持し、全選択を再実行して初回成功を合算しない。native100%/週間24%への自然回復を実確認して開始、追加reset購入使用0。

## 3. 実際に行った作業

- `packages/formats/src/vsora_formats/lba_band.py`：偏波/供給sideband Uを必須とする固定mix/filter、有界read、親/viewのtyped context guard、係数/識別copy。
- `packages/formats/tests/test_lba_complex_band.py`：独立有限和、tone/係数/seek/chunk/guard/不正値/原本変更/親とview context変更。
- `workflows/lba_complex_band_validation.py`：変更しない実4局原本・保存178 levelsと、独立係数/有限和/合成decoded toneを照合するworkflow。
- 契約、公開電圧案内、roadmap、report索引、本report、text validationを更新。

cutoffと正規化は[SciPy firwin仕様](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.firwin.html)を確認し、SciPy1.18.0を使用する。[Hilbertの正周波数振幅規約](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.hilbert.html)を有限mix/filterへ明示したが、FFT Hilbert自体は使用していない。有限FIRの鏡像漏れを0や理想解析信号へ置換しない。保持帯域3/16は参考値でhard maskではない。

## 4. 検証条件・結果

実入力は178のV177A/1600-445、4 LBA局の各1MiB/公称8MHz/0.262144秒/real2pol/2bit。PAの記録L,R、他R,Lを保持。供給USBだけを使い、物理RFや実ADC rateを推定しない。元header/offset/SHAは保持し、新取得・原本生成・SigMF/VDIF file変換は0。今回は実原本に対する有限複素帯域変換を実行する。

固定窓は `(64,1),(65,7),(1027,4096),(1028,4097),(65539,16384),(2097075,13)` を各偏波へ適用する。両端64sampleが不足する要求は拒否し、中心indexを元の名目時刻へ対応付ける。全有効sampleは2種類のchunkで同じ値・SHAになることを確認する。新相関/Closure/画像study/MCは0で、全回帰内の既存画像試験とは分ける。

事前初回は独立scalar_referenceの返却arrayをtest側がtupleと誤読し10失敗/95成功。全worker終了後に余分な添字だけを訂正し105成功。旧test/log/失敗pytest一時を管理外へ保持した。その後reviewでview自身の公開contextを変更しても処理を続けないguardと5testを追加し、事前最終110成功。filter/NCO/数値許容/原本は変更していない。旧product版と事前study1を保持し、最終productで事前study2を再実行した。

事前study2は約2.376秒/追加peak22716416byte、実48窓の独立有限和との差は最大3.798161381895825e-11 code-unit、合成tone差1.5201354410802144e-10、固定7点pass誤差3.830841889196357e-5/鏡像gain5.953381349010911e-6で許容内。合成toneは内部kernelへのdecoded実数arrayで、収録2bit波形と区別する。7点の結果を連続帯域へ拡張せず、実FFT独立性やnoise分布を導かない。

正式初回の全選択は成功し、19worker全終了。両対象各165成功/41既存種別warning、collect/full各2634成功/39404既存種別warning/除外0。source全回帰609.66秒、installed606.51秒。非上書き2workerのreturn1は意図した拒否で、既存出力SHAを保持した。事前の105/110成功を正式結果へ加算しない。

source/installedの全53NPZ fieldと方法JSONは厳密一致。実48窓の独立有限和との差は両者最大3.798161381895825e-11 code-unit、14合成tone差は1.5201354410802144e-10、固定7点pass誤差3.830841889196357e-5/鏡像gain5.953381349010911e-6。固定許容内であり、同じ有限標本・同じoperatorの代数確認である。

新wheel `70abdc16118d061e769631481d822f87682ae005356e9cb29c9703f850e00de4`、107製品+4assets全byte、3study module origin/byte、44依存版一致/pipcheck、checkout外helper不要APIと実workflow CLI、既存CAMRAS inspect-sigmf実CLI一致。旧106製品source、旧151/168/169/171/172/173/174/175/176/177/179 prefixと179初回archiveは各旧wheel byteを保持した。新installed基準は `outputs/stage181-installed-venv`。

両実Chromium各28条件/56JSON/672行/JavaScript error0/外部要求0/日本語390pxを確認。保存模擬診断の回帰であり新LBA/SigMF画面ではない。helperの固定stage137/production_changed:falseは181製品未変更を意味しない。通常GUI151更新・再起動0。

両studyのconstructor data full hashは各4file/4194304byte/1pass、viewの追加data hash0。各局の読込は1292call/4301352byte/最大8258byte。これはworkflow自身の原本再SHAや総I/O、実機throughput測定ではない。source study約2.488秒/追加peak22499328byte/保存3045819byte、installed約2.516秒/22331392byte/3045937byte。各64MiB/256MiB以内。

凍結1288file/462Python、固定入力305SHA、131原本76SHA/CAMRAS3SHA/LBA14fileと過去原本を保持。正式全体1244.81秒でattempt3600秒/全7200秒以内。pytest一時を含むworker境界最大2246367239byte。最終の補助・管理記録全体・公開textと残りtext4MiB reserveを加えた保守上限2252393430byteで4GiB内。終了・所有・lock不在・正式時刻内を確認して成功pytest一時1618829694byteだけを削除し、事前失敗証跡は保持。削除後段階保存627587127byte/空き39822647296byte（集計時点）。連続filesystem peak測定ではない。

公開監査指摘0、文書リンク2436件で欠落0。9fileのstrict allowlistで公開し、対象外tracked1615fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

出力はcomplex code-unitで物理ADC/電圧/gain/SEFD較正ではない。元の2bit収録損失を回復せず、有限帯域選択は一般に可逆ではない。供給nominal Fsを未知actual clockへ代用せず、派生sample indexの算術を実時計精度としない。実天体検出/fringe/実相関/Closure/画像、実低SNR尤度、全夜/GPUは未検証。

親の全stat保持raw変更や最後のguard後の変更、trusted Python/file lock不在の限界を引き継ぐ。原本SHAは取得fragmentだけで未取得member/archive全体のSHAやproducer認証ではない。配布用途を根拠とするローカル非再配布検証で、別個の明示data license未確認を維持する。原本/提供metadata/派生科学JSON・配列・図のGit公開0。

## 6. 次段階

このsample-domain viewをphysical-time処理へ渡す場合は、供給/推定/実測clock、sideband/RF、単位、局geometryと原本identityの対応を別契約で固定する。実clockを補い600m制限を外して既存profileへ合わせない。具体差と実残量から次作業を選び、同じcodec/有限FFT/参考fitの小変更を段階番号のために反復しない。旧画像尤度/131再fitは保留、次文書整理190/予定根本200を維持する。
