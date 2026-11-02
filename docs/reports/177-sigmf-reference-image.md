# 段階177：原本照合を保つ明示SigMF参考画像sequence

- 作成日：2026-11-02（正式完了2026-11-03 JST）
- 状態：完了（最終正式attempt2、初回中断を保持）
- 比較元コミット：`07054f57284de8e051649a08b15a49e0e624ff1d`（176）

## 読者向け概要

複数局の短い波形から、時計整列・局別rate推定・補正相関・窓結合・Closure・相対画像までを、明示したSigMF参考modeで通す。Closureは局ごとの位相や振幅の一部に依存しない組合せで、RMLはその観測量と正則化から画像を推定する既存計算である。原本識別の照合を画像終了まで保つ。

今回確かめるのは**保存模擬入力での接続と数値の一致**。既存高SNR近似を実観測の正しい誤差分布と認定する段階ではない。固定100反復でoptimizerが非収束になった結果も残し、API完了・最適化収束・画像精度を分ける。

## 1. 目的・対象範囲

176までの原本/controlと保存shardの対応を画像入口へ渡す。`process_sequence(..., sigmf_reference_image=True)` / `vsora-sequence --sigmf-reference-image` と、全source指定を伴う `image_synthesis` / `vsora-synthesis --sigmf-reference-image` を接続する。reader/codec/identity/mergerを別実装せず、既存のlive親とguarded derived viewを再利用する。

既定VDIF画像、SigMF correlation-only、175/176 merge-onlyは維持する。単窓画像pipeline/GUI/通常correlateへSigMFを追加しない。新noise model/weight/mask/Closure/RML objectiveを実装せず、旧164/165の131画像再fitや新尤度計画は保留したまま。

## 2. 完了条件

実装前に目的/入力SHA/許容/MCSE有無/時間byteと14回の専用参考画像呼出予算を管理外で固定した。

- 明示bool flagと原本全指定だけを許可し、既存局順/ID、nominal Fs、RF、供給UTCとclock offset、明示actual_rate、ADC scale1、pair/config/FFT/周波数軸契約を維持する。
- 各sequenceの元data full SHAは4file/9175040byte/1pass、子data hash0。原本と窓別controlの内容SHA/stat guardを画像終了まで保つ。閉じた逐次runのlive親だけを再利用する。
- 各窓の全NPZ/科学JSONは保存174へ一致。旧176の参考SigMF/VDIF画像へ数値・Closure・画像NPY・科学JSONを一致させる。除外は検査済み追跡SHA、今回の照合/scope診断と `runs[].elapsed_s`。他のbyte/科学fieldを除外しない。
- 独立有限画素Fourier和と共分散solveで、固定2probeのobjectiveをRTOL1e-10/ATOL1e-8、4方向ずつの勾配を独立中央差分h1e-5でRTOL1e-5/ATOL1e-7へ照合する。product選択のClosure行を条件とする代数検査で、MCSEはない。
- 両新対象/collect/full、wheel/pipcheck/全byte、checkout外helper不要API、実sequence/synthesis CLI、両実Chromiumと旧prefix保護を完了する。正式中はcode/helper/入力固定、全worker終了後だけ修正する。

## 3. 実際に行った作業

変更は `apps/correlator/src/vsora_correlator/sequence.py`、`apps/imaging/src/vsora_imaging/synthesis.py`、それぞれの既存SigMF試験、[検証workflow](../../workflows/sigmf_reference_image_validation.py)、[session契約](../../interfaces/sigmf-session.md#明示した高snr参考画像sequence177)、[結合契約](../../interfaces/sigmf-spectral-merge.md#原本照合を保った参考画像177)、[取得案内](../guide/public-voltage-data.md)、計画/索引/本report/text validation。

新flagはstrict boolで、correlation-onlyとの併用・VDIFへのTrue・sourceの一部指定・caller SHA辞書を拒否する。SigMF画像の暗黙許可を閉じる。旧176のunverified SigMF画像は旧prefixで比較参考としてのみ実行する。通常のVDIF画像は既定のまま。

原本をfresh hashするlive親をpilot/final/結合で共有し、親と各窓control viewを結合・Closure・画像fitの各境界/終了後に検査する。結合出力のreuse診断はroot累計なのでsequence/窓の反復値と加算しない。ここでの1pass/byte量はSHA読込の計数で、相関readを含む総I/Oや実機速度・全夜throughputの測定ではない。無情報や画像中の原本/子control変更はpartial/failureを保持し、完成directoryへrenameしない。

## 4. 検証条件・結果

### 固定入力と参考計算

174の相互に異なる模擬4局140有効frameを一度だけ派生したSigMFと元038 VDIF、供給clock/session、完成2窓shardを全SHA再利用した。尺度 `2*byte-255` はcode unitで、物理ADC/SEFD較正ではない。Fs2.048MHz/各573440complex sample/.28秒/data計9175040byte。原本生成/変換/取得0、131は76SHA照合だけで再生成/再相関/再fitしない。CAMRAS実単局原本は保持し実基線0。

FFT32/pilot128blocks×64/start.002/.130/final.1/step.128/max100Hz/constant/raw U3は174と固定。画像は32pixel/16arcsec、starts1/max_iterations100、seed21、prior FWHM240arcsec、entropy .01、TSV .0001、centroid .1。truthを係数/格子/seed/weight/実効Mへ合わせない。174原本の新API再相関は接続検査で、独立な実観測試行/MCではない。

旧176 installedによる参考2画像と事前study2画像は初回に数値照合成功。事前の既存対象60成功、追加後67成功、子control境界と無情報/暗黙入口の拒否を含む最終69成功。旧176のunverified画像経路を新製品の公開入口にしない。正式前の文書置換1回のcontext不一致は無変更で、実試験/正式worker失敗ではない。

独立参照は中心delta95%+uniform5%、中心delta90%+Gaussian prior10%の固定2probe。truth画像ではない。w項を含む1024画素の有限Fourier和、保存観測weightからのbaseline variance、product選択行のfull同種cell内共分散を独立solveする。wrapped phase/logamp二次損失、entropy/TSV/centroidを別計算し、productのFourier/covariance factor/objectiveを参照計算に使わない。行選択と観測値を条件にしている。事前最大objective差2.220446049250313e-16、方向勾配差5.182905059991638e-11。固定観測objectiveの代数検査で、統計的校正の検査ではない。

134/145の八条件に対する今回の範囲は次のとおり。新しい尤度を採用する判定には使わない。

| 条件 | 今回の範囲と残る前提 |
|---|---|
| 前方平均 | 保存2窓の全相関値は旧有限計算と同じ。画像probeの画素Fourier和は独立照合。未知天空の有限時間平均の一致は未検証 |
| 単位 | code-unit由来ADC²から相対unit-sum画像へ接続。実ADC/SEFD/絶対fluxは未較正 |
| 共通標本集合 | 保存field/mask/countを変更しない。countを独立標本数へ読み替えない |
| 時間周波数依存 | 時間/channelを平均せず保持。既存RMLのcell間独立近似は残す |
| 未知局量/推定 | 既存pilot/rate推定を使用。同じ波形による推定依存や未知実gain/LOを新しく解決しない |
| SNR選別 | productの選択行を条件にする。選別後coverageや誤差分布は未検証 |
| joint Closure | 既存の同種cell内full covarianceを維持。phase/logamp間やcell間のjointモデルは追加しない |
| objective/勾配 | 固定観測行とcovarianceで独立代数検査。新noiseモデルの正規化/微分ではない |


正式attempt1はreviewでAPI probeが既定min_snr=10をsettingsへ省略し、CLIが明記する記録差を検出したため、所有coordinator/workerへSIGINTを送った。installed全回帰はreturn2で中断した。全worker終了後だけAPI probeに既定値10を明示し、製品/入力/数値条件/許容を変えずattempt2で全正式選択を再凍結・再実行する。初回log/部分出力/freeze/wheel/prefixを保持し、成功を合算しない。停止補助の最初のpsutil import失敗は作用0として転記保存し、標準Python/procで所有を照合して停止した。

専用画像呼出は旧baseline2+事前2+最終正式10の14回に、初回正式study両4/API両2の6回が加わり、総20回へ最終正式前に予算を改訂した。unit/full中の画像試験とは分ける。全attempt7200秒/全保存2GiBは維持した。

最終正式attempt2は両対象124・collect/full各2524成功、各39404警告、除外0。source627.73秒/installed631.31秒。警告の種別と文面2組は旧176の全回帰と一致し、新しい種別/文面はない。27workerが終了し、非上書き6件のreturn1だけが意図した拒否。初回の成功は加算していない。

source/installedは229個のNPZ field（schema/metadataを含む）と2画像NPYが厳密一致。補助のcompared_arrays=292は画像fieldを再確認したassert回数で、独立field数として扱わない。窓別の保存174対照は各42field/8JSON×4窓、旧176参考画像はSigMF32/legacy31field（NPY各1を含む）を照合した。追跡SHAを実fileへ照合し、科学field/byteを他に除外しない。175/176のdefault/verified mergerも全44field/JSONが旧176へ一致した。

新SigMF sequenceの原本hash実呼出4回/9175040byte/1pass、子data hash0。Closure選択42行（phase32/logamp10）を条件に、2objective/8方向の独立参照は固定許容内、最大差は事前と同じ2.220446049250313e-16/5.182905059991638e-11。両参考画像はfinite/非負/unit sum1とFITS検査を通過したが、いずれも100反復の上限に達しoptimizer_success=false。非収束を成功へ置換しない。

wheel SHA256は `bf09a3576185a8552ece865f65b0f56e2ba3e18a9e4bcdfa6d2ee16d5cab7243`。105製品+4assetsのsource/wheel/installed全byte、31study module origin/byte、44依存版一致、pipcheck、checkout外helper不要API、実sequence/synthesis CLIが成功。新installedは `outputs/stage177-installed-venv`。旧151/168/169/171/172/173/174/175/176 prefixはそれぞれ旧wheel全byteを保持した。

両実Chromium各28条件/56JSON/672行/JS0/外部0/日本語390px。保存模擬診断のGUI回帰で新SigMF画面ではない。固定helperのstage137/production_changed:falseは177製品未変更の意味ではない。正式調整役の最終stdoutには転記残りのSTAGE176ラベルがあるが、実path/全検査/進捗/wheelは177。原stdout/freezeを変更せず正式後の訂正注記を保存した。

凍結1280file/454Python、固定入力234file、131原本76SHA、CAMRAS3SHAを保持。study追加peakはsource95178752/installed95416320byteで256MiB内、両study保存6199345byteで64MiB内。初回保存を含む全追加保存集計1238567380byte/空き39824846848byteで2GiB/10GiB reserve内。両attemptの経過2836.43秒で全7200秒内。新録音取得/変換/生成/実基線/新MC trial0。

[text validation](../../validation/runs/stage177/README.md)に再現方法を記載。波形、metadata、科学JSON、画像、図、ログ、凍結表は管理外に保持する。

公開監査指摘0、文書リンク2369件で欠落0。12fileのstrict allowlistで公開し、対象外tracked1594fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

全statusを保存した参考画像は固定100反復の上限に達しており、optimizer収束の合格ではない。有限値/非負/unit sum1/FITS相対単位/旧計算一致と、正しい実画像や最適解の保証を区別する。固定観測の高SNR covarianceと独立baseline近似、同種同cellの相関だけを使う既存RMLを変えない。実際の時間周波数依存、低SNR/位相branch境界、未知局量、beam/RFIや採否込みの新尤度は検証していない。134/145の八条件が形式接続で満たされたとはしない。

SHA/guardは現物と保存識別のsnapshot照合で、配列の計算履歴やproducer認証ではない。raw全stat保持変更・最後の検査後の変更・永続file lock不在・trusted Pythonの前提は残る。供給値の1ns整合/9桁保存は実時計測定ではない。valid_fft_countは独立標本数/実効Mではない。

実RTL-SDR/OCXO・1.42GHz Cas A・最大600mからの画像復元、未知実LO/gain/SEFD、実FFT独立性、全夜GPUは未検証。相対画像へ精密gain/絶対fluxを一律必須にしない。通常GUI151は更新/再起動せず、専用GUIは保存模擬診断の回帰であり新SigMF画面ではない。

## 6. 次段階

主経路に残る未知実入力のnoise/時間周波数依存/採否と、既存高SNR近似の適用範囲を具体的にreviewする。同じ画像fitの反復や収束条件の後付け緩和で実観測不足を埋めない。次候補のread-only調査で[DiFX公式配布案内](https://github.com/difx/difx/wiki/datasets)から匿名FTPのlba_4MHz一覧を確認し、README/入力設定20863byteと一覧だけを管理外保存した。録音本体160010240byteは取得していない。説明上は複数LBA局の較正天体記録だが、現物波形は未確認。個別利用条件・最小取得範囲・新形式の受入を固定する前には取得/製品採用しない。167のLSL候補は既確認のため重複採用しない。複数アンテナ原本は観測ID/最小byte/利用条件がそろった場合に少量取得を選ぶ。実入力待ちだけで監視へ戻らず、具体的software差と正式予算から選択する。文書整理180/予定根本200。
