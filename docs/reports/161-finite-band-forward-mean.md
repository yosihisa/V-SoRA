# 段階161：同時混合した3線スペクトルと有限平均

- 作成日：2026-10-30
- 状態：完了（既知3mode・固定符号probeの平均参照）
- 比較元コミット：2f6a60d27137e126c77048e7494e628a73bd43ff（160）

## 読者向け概要

短いFFTのチャネルには複数の周波数の波が入ります。各周波数が同時に存在すると、一つの有限入力にはmode同士の交差項も現れます。周波数ごとの電力を足すモデルと比較するには、どの平均でその交差項を消すのかを明示する必要があります。

今回は3本の線スペクトルを各入力内で混ぜ、事前固定した4つの符号probeで平均しました。この有限平均は独立な周波数和と実整列APIに一致しました。**連続した広帯域のPSD積分や、実電圧のGaussian性・雑音分散を検証したものではありません。**

## 1. 目的・対象範囲

049/055/059/061/074/076/078/100/141/142/146/152/159の関連code/test/workflow/validationをreviewしました。142は共通の局共分散Sと周期mask、152は任意modeを分けた有限平均、159は単一toneでした。今回は、周波数ごとに変わる供給点形状の空間位相と、FIR/補間/有限チャネル応答を、同時混合rawの有限平均へ結ぶ差分を選びました。

新[workflow](../../workflows/finite_band_mean_validation.py)、本report/索引/roadmap/[小容量記録](../../validation/runs/stage161/README.md)のみ変更。159の`tone_response`検証helperを再利用し、新製品APIを作らず159のrunも再実行していません。RML/尤度/weight/GUI、既存原本を変更しません。

## 2. 入力と完了条件

3局/raw512sample、Fs2.048MHz、FFT8×16block、start96/Fs、span62.5µs。159と同じ固定合成UVW/delay、合成decoded64sample frame・全valid・seekFalseを使い、実manifest/時計JSON検査、SampleBufferのFIR状態/guard/補間、RF補正、FX/saveを通しました。

主比較では実Astropy/EOP/地理変換、codec/量子化/header/seek、上位InputIdentity、未知clock/LO推定は実行していません。通常APIのVDIF/geometry説明ラベルを、その実行証拠にはしません。131high_aのmetadata2件をSHA固定して借り、最初の3VDIFは所在検査だけでpayload不使用。新検証metadataと8保存相関を作り、原本131の76SHAを保持し再生成/再相関していません。

供給点形状は8×8/64arcsecのoff-axis(1,6)、記録用観測profileは元の32×32/16arcsecです。時計actual=nominal/offset0、rate0/gain1/受信機雑音なし。元の仮定SEFDは使わず、normalized点形状とADC²を絶対Jy較正へ読み替えません。SK/RFI選別を同時に変えず、新manifestのspectral_qualityを外し、RF guardのweight0を残した全チャネルvisを比較しました。保存weightsを使ってprobeの平均を重み付けしていません。

### 固定した有限ensemble

```text
f/Fs = [-89, 25, 108] / 512
線電力fraction：uniform=[1/3,1/3,1/3]、colored=[.1,.3,.6]
符号H = [[1,1,1], [1,-1,-1], [-1,1,-1], [-1,-1,1]]
```

各probeは `sum_m H[p,m] sqrt(w_m) raw_mode_m` とし、必ず3modeを同時に含みます。4符号の列mean0、`H^T H/4=I` を確認しました。実符号なのでpseudo-momentもIで0ではなく、proper complex/Gaussian標本ではありません。入力の各局各sampleについて、有限mean0・有限平均power1を確認。これは構成した恒等式で、独立時刻の測定結果ではありません。

wは各線の電力質量の配分で、連続PSD/Hzではありません。二配分は同じ符号/周波数/点形状を共有し、8API呼出もsource/nativeも独立観測数として数えません。MC0、seed/MCSE対象外です。

## 3. 独立計算と実API

各modeの独立定常tone応答A_s(f)、実周波数RF+fでの点空間位相、8項の直接DFTから、補正電圧とprobeごとの保存visibilityを計算しました。別に、有限平均の参照を

```text
V_k,ij = sum_m w_m K_km A_i(f_m) conj(A_j(f_m))
                   * exp(-2πi (RF+f_m)(Delta_j-Delta_i))
```

で構成しました。Kは有限DFT和の二乗normです。各modeの全チャネルsumK=8はunitary正規化で、実帯域/IID数/flux補正係数ではありません。mode周波数とchannel中心周波数での既存`direct_visibility`も独立point和へ照合。主比較のRML/Closure評価・勾配・fitは呼んでいません。

全補正電圧、各probe vis、直接DFT平均、mode別電力和、実4probe平均を固定RTOL1e−9/ATOL1e−10で照合。point和の照合はRTOL1e−11/ATOL1e−12です。空間位相だけをchannel中心に置換しA/K/wは同じにした近似負対照の全8channel/3基線の相対差は、固定1e−6超を要求しました。周波数/配分/係数を結果から選び直していません。

## 4. 結果と正式検証

| 線電力配分 | 実平均−mode和 最大絶対差 | channel中心位相近似の相対差 | 単一probeと有限平均の相対距離範囲 |
|---|---:|---:|---:|
| uniform | 1.343e−12 | .000460092 | .019482〜.066042 |
| colored | 2.420e−12 | .000443642 | .001665〜.037031 |

単一probeには交差項が残り、固定4符号で平均するとmode別電力和と一致しました。単一probeとの差は、この決定論的入力の干渉の記述であり、雑音誤差率/選別bias/実機較正ではありません。channel中心近似との差も、実画像NRMSEやRML不具合、131画像差の単一原因ではありません。

全probeの最大補正電圧差5.19e−13、保存vis差2.45e−12以下。初回正式手順で成功し、新unitなし。MC0は主比較を指し、既存対象内の乱数・時計推定試験と区別します。両既存11対象、source1.19秒/installed.75秒、警告0・除外0。全科学JSON/[21配列](../../validation/runs/stage161/arrays.npz)と、各8保存NPZの80フィールド(metadata含む)が完全一致しました。

24製品moduleの正確source/prefix/byte、native checkout外/runner/PYTHONPATHなし、非上書き2を確認。159 helperはcheckoutを要する検証依存で、製品moduleの導入prefixと区別します。旧459+newworkflow凍結460、metadata2/原本131の76/対象外tracked1530/引用44fileのSHA保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103+4assetsのsource/wheel/installed全byte不変です。

study本体wall約.0415/.0376秒、生涯peakRSS132747264/133316608byte、保存125994/126658byte。各worker120秒/追加64MiB/公開512KiB/段階1200秒内。単独study process内の8API呼出であり、8独立OS workerではありません。保存量/生涯RSS/単発wallを全夜/GPU/必要PCへ外挿しません。公開監査指摘0、文書リンク2195件で欠落0。

[全結果・入力/一次コードSHA](../../validation/runs/stage161/reference.json)、[正式検証](../../validation/runs/stage161/verification.json)。新full/collect/wheel/install/browser/VDIF生成decode/MC/画像fitなし。新保存相関は小さい合成decoded入力の参照です。最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告の引用で今回へ足しません。通常GUI151も変更していません。

## 5. 制約と次段階

固定幾何・供給点・3本の線スペクトルと有限符号平均だけの接続です。連続PSD積分、Gaussian noise共分散/coverage、実131の8局4ms1024block/.3〜3秒は未校正。159/161のdecoded参照と153の別集合codecを、統合した実主経路の成功へ合成しません。

八条件、実Cas A、未知実LO/gain/SEFD、beam/RFI、実FFT独立性、低SNR画像尤度、全夜GPUは未検証。新production尤度/RML/画像再fit/GUI、外部追加反復、truth係数調整、Windows収録は保留です。

次162は、同じ有限電圧で量子化と整列平均の間に新しい差があるか、004/006/014/153/159/161等と実codecを先にreviewする候補です。同等なら重複せず目的を改訂します。非線形量子化後にmode別の和を無条件に継承せず、実codec/float32/scale/clipと独立参照のどこを照合するかを正式選択前に固定。実入力新回答優先、148質問は繰り返しません。次文書整理170/予定根本レビュー200、前提が崩れれば前倒しします。
