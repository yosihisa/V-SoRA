# 画像雑音モデルを接続するための適用判定（145）

基準は144（`db8dca3`）。[134のモデル・保存量契約](image-statistics-contract.md)を現在の一次コードと141〜144の記録へ照らした追補である。134の当時の監査記録は変更していない。これは文書上の適用判定であり、新しい実行時ゲート、統計API、尤度、画像化器ではない。

**現時点では、141〜144の参照結果をproduction RMLの新しい雑音モデルへ接続しない。** 小さい既知モデルの確認、保存情報の整合、実入力での誤差分布の校正は別の証拠を要する。現在の高SNR近似による相対画像の経路は維持し、低SNR画像尤度や実機のconfidenceを新しく保証しない。

## 1. 現在の消費側から読む

| 処理 | 一次コードで確認した入力・計算 | 適用判定への意味 |
| --- | --- | --- |
| 整列 | `SampleBuffer`は実sample rateに応じた65tap FIR、状態と有効supportを保持する。`correlate_aligned`は各sampleの幾何delay・供給clockからquery位置を作り、RF/rate位相を掛ける | 固定offsetのkernelだけで一般の処理全体を代表したとはいえない |
| FX | 非重複FFTを`norm='ortho'`で計算。局powerは局有効集合、crossは二局の共通集合で平均。weightは名目件数と観測power積から作る | 非重複というだけでFIR後の独立性は導けない。quality設定によりweightのpowerはchannelまたはtotalを使う |
| 047診断 | power・単位・局ID・全基線・count・flag・PSD等を検査し、046から044を呼ぶ | `conditional_estimate`は仮定付き診断。外側stateと内側`closure_joint_valid`は別である |
| production Closure | `snr=abs(V)*sqrt(weight)`で基線を選ぶ。同種Closure内では共有基線の非対角共分散と独立な行を使う | 基線独立近似を起点とする。線形独立な行が統計的に独立とは限らない |
| RML | uvw・visibility・weight・pairから構築時にClosure、採用行、共分散を固定する。各cellのphase/logampを別々に加算する | 047のJSONや044のjoint共分散を読む接続はない。一般の基線間、phase/logamp間、別cell間の雑音を全部使っている構成ではない |
| 画像前方モデル | 点画素のuvw Fourier式にw項があり、非負・unit flux画像を使う | w項の欠落を原因としない。有限時間・帯域・filter・量子化を含む電圧生成からの平均との一致は別に必要 |

消費側の[整列](../apps/correlator/src/vsora_correlator/aligned.py)、[FX](../apps/correlator/src/vsora_correlator/stream_fx.py)、[047](../apps/correlator/src/vsora_correlator/noise_diagnostics.py)、[Closure](../apps/imaging/src/vsora_imaging/closure.py)、[RML](../apps/imaging/src/vsora_imaging/rml.py)を確認した。23ファイル・47関数/メソッドの正確な行範囲とSHAは[一次コード記録](../validation/runs/stage145/source-audit.json)に保存した。製品関数を新しく実行した監査ではない。

## 2. 単位と正規化を混ぜない

- visibilityが`ADC^2`なら誤差共分散は`ADC^4`、`Jy`なら`Jy^2`。047は局powerとvisibilityの単位一致を要求するが、単位ラベルだけで実I/Q・感度を較正したことにはならない。
- phaseはrad、log amplitude Closureは無次元。対応するjoint行列の順序と単位も保持する。一般のvisibility共分散の対角を、そのままClosureの分散へ渡さない。
- production weightはquadrature逆分散の弱信号近似。044は全Re/Im共分散の対角から平均quadrature分散を使う。同じ数値の閾値でも同じSNRになる保証はない。`form_closures`と047の既定値は5、RMLの既定値と135/144のproduction比較は10である。
- 現RMLの出力は相対flux/pixel。一定の局係数をClosureで消す性質は、区間内変動、未知SEFD/beam、局応答を含む電圧共分散Cの同定を代行しない。

133のfitter入力は元相関の7科学配列と最小表示metadataを保持し、局power/count/flagを画像側へ渡していない。条件付き診断は完全な元相関へ戻る。画像入力へ真値天空・LO・SEFDを混入して、この不足を埋めない。

## 3. 141〜144で成立したことと、残る接続差

以下は保存済み正式記録の引用で、145でMC・再相関・fitを実行した結果ではない。

| 証拠 | 確認された範囲 | 実入力へ移す際の不足 |
| --- | --- | --- |
| [141](../docs/reports/141-colored-fft-noise-reference.md) | 既知3tap入力FIRと固定局offset、4局/FFT8/16block。既存049へ合成kernelを渡し、独立なdense traceと実FIR/sinc/FFT、各color4096試行を照合 | 131の周期帯域制限とは入力モデルが異なる。時変query/phase・量子化・mask・実効M/coverageは未校正 |
| [142](../docs/reports/142-periodic-fft-noise-reference.md) | P512の既知周期bandlimitと固定小operatorの4096試行。Dirichlet閉形式・周波数投影・traceを照合。131公称P6225920と無限周期は小operatorの計算のみ | 4局/16blockはFs2.048MHzなら62.5µs。131の8局/4ms/1024blockや0.3〜3秒の原本処理を校正していない |
| [143](../docs/reports/143-pilot-rate-holdout.md) | 保存4pilotの固定parity。各375学習/374未使用、8profile/32系列。真値LO/sky/gainを推定へ渡さず、範囲外拒否も保存 | 同じraw・周期・filter境界・clock/gainを共有する。独立rawや推定依存の除去ではなく、比の支持も異なり得る |
| [144](../docs/reports/144-observed-snr-selection.md) | 既知IID Gaussian3case各4096、全試行の平均/MSE/平均推定共分散は固定6MCSE内。採用群は記述として分離しN0の10群を保持 | 全試行の性質を採用群へ移せない。有限例の平均誤差やMSEの比を画像weightの補正係数へ使わない |

144のrho0.45・joint triangle5では878採用、固定baseline実部の平均誤差約0.0868、真値からのMSE約0.01235、平均推定分散約0.00980だった。rho1.6・joint triangle10は738採用、約0.2088/0.06274/0.04230。MSEと選別後平均からの中心化共分散を区別する。joint10とproduction10のmaskは固定例でbaseline36/triangle26試行が異なった。この結果は一般の補正率やcoverageを与えない。

## 4. 八つの接続条件

| 条件 | 現在の根拠 | 採用前に必要なこと |
| --- | --- | --- |
| 前方平均 | 点画素uvw式の一致、既知電圧の有限参照 | 時間・帯域・filter/補間後の平均を同じ入力/幾何で照合し、未知局応答の扱いを定める |
| 単位 | metadataと配列の単位契約 | モデル・観測・共分散の単位/正規化、実I/Q/SEFD/beamを区別する |
| 標本集合 | producer定義の下で全局countと完全な全pair共通countがMなら共通集合。135は36条件付き/60inactive | 共通集合とは別にIID・平均0・proper Gaussian・一定Cを検討する。PSDだけで来歴を証明しない |
| 時間周波数 | 141/142の既知固定小operator | 実際の時変query/phase、量子化、欠損・選別、channel/cell間の依存を扱う。名目Mをtruthに合わせない |
| 未知局量と推定 | 143の事前分割と共有条件の記録 | 未知gain/LO/SEFDを推定・消去・周辺化する対象と、学習/評価の依存を定める |
| 観測値による採否 | 144の全試行と採用群の差、047の内外の区別 | 採用後の母集団・誤差分布を定義する。選別前の不偏性やSNR閾値をconfidenceへ読み替えない |
| Closureのjoint性 | 044は全Re/Imからphase/logampを同時に一次伝播 | 無効/冗長行、特異な共分散、基底、分岐境界と低SNR分布、別cellの関係を定める。ゼロで埋めた無効行を誤差0の測定にしない |
| 目的関数 | 現RMLは固定観測共分散、100は既知Cの電圧尤度 | 新しい確率モデルとsupport/正規化、共分散のパラメータ依存を採用するか定め、独立なobjective・勾配・拒否を先に照合する |

[判定一覧JSON](../validation/runs/stage145/applicability.json)はこの文書の記録であり、ソフトの新しいpass/fail APIではない。

### 共分散行列の差し替えだけで済ませない

044は冗長行を含むjoint行列を返し、逆行列を計算しない。046のensemble不偏性も、Closureの非線形変換後の不偏性や選別後のconfidenceを保証しない。

現RMLは構築時に観測共分散を固定する。一方、[100の既知C参照](known-covariance-gaussian.md)は共通IID電圧に対する`M[logdet C + tr(C^-1 S)]`を既に実装している。これは電圧の負の対数尤度からC非依存定数を除いた値で、Sの正規化密度でも現在のClosure画像尤度でもない。未知局量、非IID、採否、画像依存のCを決めずに100を加算しない。新モデルを採用する際は、そのモデルの正規化と微分を定める。これは現行の固定共分散目的関数に新しい不具合を再現したという主張ではない。

## 5. 次に何を確認するか

146では画像fitを増やす前に、**固定offset参照と実際に変わるquery係数の未接続部分**を最小条件へ分ける。既存049の直接FIR/FFT、055の既知時間共分散、059/061/078の三次統計、clock/FX試験を先に点検する。異なる統計量の実装を重複せず、同等の検証があれば目的を改訂する。

候補は、幾何とrate補正を固定したまま供給clockの傾きだけを変える小さい有限作用素の対比較である。入力共分散、query原点、tap・FFT正規化、guard、評価量、許容差、反復の有無、時間/byte予算を実行前に固定する。直接係数の計算と実FIR/補間/FFTの照合を先に行い、量子化・未知推定・観測SNR選別を同時に変えない。既知係数の確認を実効Mや実機の校正へ拡大しない。

146の受入条件を満たしても、この表の他の不足が自動的に解けるわけではない。新しい画像比較とGUI接続は適用条件が揃うまで保留する。実機の利用と測定手段を確認できれば実入力の項目を前倒しする。150で文書整理と専用根本レビューを行い、実目標への寄与と次の5〜10段階を見直す。150自体は今回実施していない。
