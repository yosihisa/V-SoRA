# 1.42 GHz・600 m基線：自作範囲と流用ソフト候補

調査日：2026-10-02。対象はOCXO改造RTL-SDRを使うCas A観測網。公式ドキュメント、開発元リポジトリと一部の公開ソースを確認した。候補ソフトのダウンロード、インストール、実行、互換性試験は実施していない。以下の優先度は調査に基づく判断であり、動作保証ではない。

## 1. 方針

相関器と画像復元は既製品を使える可能性が高い。自作の中心は、改造受信機に合わせた収録管理、サンプル時刻と欠損の管理、IQと観測メタデータを既存ソフトへ渡す接続部分、および受信機固有の誤差を再現するシミュレーターである。VDIFやFITS-IDIの低水準入出力まで一から書く必要はない。

1.42 GHzでは波長は約0.211 m。600 mに対する `λ/B` の概算分解能は約73秒角＝1.21分角。約5分角のCas Aに対して大まかな構造の復元を検討できるが、実際のビーム・画像品質は投影基線、短い基線、局数、観測時間、感度に依存する。この数値は計算による見積りであり観測結果ではない。

## 2. 自作が残る場所

| 工程 | 流用範囲 | プロジェクト側で実装・設定する部分 |
| --- | --- | --- |
| RTL-SDR制御・IQ取得 | librtlsdr、Pythonラッパー、GNU Radio等 | 観測スケジュール、設定記録、ファイル分割、局識別、収録状態管理 |
| 時計・サンプル時刻管理 | 同期・相互相関の参考実装はある | OCXO配線に対応した時計モデル、開始時刻推定、サンプル番号と時刻の対応、欠損区間管理。ハードウェア側の追加設計が必要になる場合もある |
| IQ→VDIF | Baseband / vdifio等 | RTL-SDRの量子化値、I/Q順序・符号、周波数向き、フレーム構成、無効データの扱いを合わせる変換とメタデータ生成 |
| 遅延モデル・相関 | DiFX / SFXCで大部分を流用可能 | 独自局の座標・周波数・偏波・時計補正を設定へ変換。既製相関器の入力で扱えない誤差は前処理や再相関で対処 |
| FITS-IDI出力 | difx2fits、JIVEツール、LSL writer | 自作相関器の場合に局・天体・周波数・時刻・UVW・重み・偏波・振幅規約を正しく渡す接続 |
| 較正・画像復元 | CASA / AIPS / WSClean等 | 自作装置のゲイン・バンドパス・位相校正手順、単一偏波の解釈、フラグ、画像化設定 |
| visibilityシミュレーション | CASA / pyuvsim / OSKAR / eht-imaging等 | 局配置、Cas Aモデル、観測条件・ビーム・ノイズ設定 |
| IQシミュレーション | 乱数・FFT等の数値部品は流用可能 | 既知の相関を持つ局ごとの確率的電圧信号、幾何遅延、LO差、サンプルレート差、位相ドリフト、量子化、欠落を再現する部分 |
| 検証記録 | Git・設定ファイル・既存可視化ツール | 実行条件と参照値、比較指標、入力・出力・ソフト版の対応管理 |

標準librtlsdr受信APIにはADCサンプル対応のハードウェア時刻引数がない。[API](https://github.com/osmocom/rtl-sdr/blob/master/include/rtl-sdr.h) 改造機の時刻機能は未確認であり、PCのUSB受信時刻、GNSS/PPS時刻、実サンプル時刻を区別して設計する。PPSを用意しても、そのPPSに対応するサンプル番号を特定する仕組みは別途必要。

## 3. 候補一覧（34件）

「主候補」は工程の中核候補、「部品」は組込み用、「参考」は追加改修や用途の見直しを前提とする。全件が実行未確認。各行のリンクは確認した一次資料に対応する。

### 3.1 収録・受信機制御・同期

| ID | 候補・リンク | 利用できそうな範囲 | 注意点・採用前の確認 |
| --- | --- | --- | --- |
| C01 | [Osmocom rtl-sdr](https://github.com/osmocom/rtl-sdr) | 主候補。Cライブラリ、rtl_sdr等によるIQ収録 | サンプル時刻管理は追加が必要。改造機・チューナーとの適合を確認 |
| C02 | [RTL-SDR Blogドライバー](https://github.com/rtlsdrblog/rtl-sdr-blog) | 主候補。Blog V3/V4向けの機器対応 | 実機モデル次第。独自OCXO改造の動作や位相安定を保証するものではない |
| C03 | [pyrtlsdr](https://github.com/pyrtlsdr/pyrtlsdr) | 部品。librtlsdrのPythonラッパー、試作収録器 | 連続収録速度とバッファ処理の確認が必要。時刻機能は基盤ドライバーに依存 |
| C04 | [GNU Radio](https://github.com/gnuradio/gnuradio) | 主候補・部品。収録、FFT/PFB、フィルター、リサンプリング | 観測用フローグラフとタグ設計が必要 |
| C05 | [gr-osmosdr](https://github.com/osmocom/gr-osmosdr) | 部品。GNU RadioからRTL-SDRへ接続 | GNU Radioとの版整合、採用するRTL-SDRドライバーとの組合せ |
| C06 | [SoapyRTLSDR](https://github.com/pothosware/SoapyRTLSDR) | 部品。SoapySDRを介した受信機アクセス | 共通API経由でも、実機にないハードウェア時刻機能は得られない |
| C07 | [rtl_coherent](https://github.com/tejeez/rtl_coherent) | 参考。共通クロックと共通ノイズによる時刻差・LO位相差校正 | 共通基準と同時校正信号を前提とする。独立OCXO・600 m分散網にそのまま適用できるとは限らない。古い実験ドライバーへの依存あり |
| C08 | [HeIMDALL DAQ](https://github.com/krakenrf/heimdall_daq_fw) | 参考。KrakenSDR向け多チャネルコヒーレント収録・同期 | KrakenSDRのハードウェアを前提にする。独立した改造RTL-SDR網向けには設計変更が必要 |

### 3.2 VDIF入出力・収録データ転送

| ID | 候補・リンク | 利用できそうな範囲 | 注意点・採用前の確認 |
| --- | --- | --- | --- |
| C09 | [Baseband](https://github.com/mhvk/baseband)、[VDIF読み書き例](https://baseband.readthedocs.io/en/stable/vdif/index.html) | 主候補。PythonでVDIFを読み書きし、変換器や検査器を作る | 使用する複素8 bit等のモード、量子化規約、フレームと時刻精度を確認。収録時刻を自動で復元するものではない |
| C10 | [DiFX vdifio](https://github.com/difx/difx/tree/main/libraries/vdifio) | 部品。C/C++でのVDIFヘッダー処理・ストリーム整形 | RTL-SDRのIQを渡す変換部分は追加。ユーティリティごとの対応モードも確認 |
| C11 | [DiFX mark5access](https://github.com/difx/difx/tree/main/libraries/mark5access) | 部品。既存VLBI形式の読出し・デコード・検査 | VDIF writerの全面代替とは扱わない。具体的デコードモードを確認 |
| C12 | [jive5ab](https://github.com/jive-vlbi/jive5ab) | 参考・部品。VLBIデータ記録と転送 | RTL-SDR制御やサンプル時刻生成を行う完成収録器ではない。小規模ローカル収録では不要な可能性もある |

### 3.3 相関器と相関処理の部品

| ID | 候補・リンク | 利用できそうな範囲 | 注意点・採用前の確認 |
| --- | --- | --- | --- |
| C13 | [DiFX](https://github.com/difx/difx)、[公式ガイド](https://difx.readthedocs.io/en/stable/) | 主候補。VDIF入力、遅延補正・相関、difx2fitsによるFITS-IDI出力 | MPI等の導入と独自局の設定生成が必要。具体的な複素サンプル・bit深度・帯域での互換性は未確認 |
| C14 | [SFXC](https://github.com/jive-vlbi/sfxc)、[JIVEチュートリアル](https://jive-vlbi.github.io/sfxc_workshop_2025/) | 主候補。実運用VLBI相関器の別系統 | VEX・制御ファイルの作成が必要。相関出力は専用形式で、MS/FITS-IDIへは別ツールを使用。採用VDIFモードは確認が必要 |
| C15 | [LSL](https://github.com/lwa-project/lsl)、[FXMaster実装](https://github.com/lwa-project/lsl/blob/main/lsl/correlator/fx.py) | 部品。時系列から周波数とvisibilityを生成するFX処理。複素IQと中心周波数の扱いがソースにある | LWA由来の局・アンテナモデルを本観測網へ合わせる必要。局ごとの時計差、長時間の遅延追跡、VDIF読込みまでの完成系ではない |
| C16 | [PyFX](https://github.com/leungcalvin/pyfx-public) | 参考。Python VLBI相関器、遅延モデル利用・相関処理の設計参考 | CHIMEのBBData/HDF5を前提とし、短時間トランジェント向け。RTL-SDR/VDIFと連続天体観測への入力・出力改修が必要 |
| C17 | [xGPU](https://github.com/GPU-correlators/xGPU)、[処理範囲の説明](https://raw.githubusercontent.com/GPU-correlators/xGPU/master/README) | 部品。FXのX段に相当するGPU相互乗算 | FFT/PFB、遅延補正、VDIF入出力、FITS-IDI出力は別途必要。CUDAとGPUの版対応も未確認 |
| C18 | [gr-clenabled](https://github.com/ghostop14/gr-clenabled) | 部品・参考。GNU RadioのOpenCL相互相関・FFT等 | 天文学的遅延モデルやvisibility出力まで含む相関器ではない。GNU Radio/OpenCL環境との互換性確認が必要 |
| C19 | [spectro_radiometer](https://github.com/ccera-astro/spectro_radiometer) | 参考。RTL-SDRを含むSDR向け電波天文・相関モード。1.42041 GHz設定例がある | 多局VDIF→FITS-IDIの完成系ではない。文書にはUbuntu 18.04・Python 2系の手順があり、現在の環境へ移植が必要な可能性 |

### 3.4 FITS-IDI出力と他形式への接続

| ID | 候補・リンク | 利用できそうな範囲 | 注意点・採用前の確認 |
| --- | --- | --- | --- |
| C20 | [JIVE jive-casaツール群：j2ms2 / tConvert](https://jive-vlbi.github.io/sfxc_workshop_2025/correlation_post.html#export-to-fits-idi) | 主候補・部品。SFXC専用出力→MS→FITS-IDI。MSからのIDI出力の別経路候補 | MSが表現できる全情報をIDIへ出せるわけではない。自作MSへの適用は条件確認が必要 |
| C21 | [pyFitsidi](https://github.com/telegraphic/pyfitsidi) | 参考。CASPER相関器向けFITS-IDI writerとテーブル構築例 | **2016年に保守終了を明記**。旧pyFITS依存。現在環境でそのまま使える候補とは扱わない |
| C22 | [Astropy FITS](https://docs.astropy.org/en/stable/io/fits/index.html) | 部品。IDI writerのFITSテーブル構築・読出し基盤 | FITS-IDIの意味・必須テーブル・規約は自分で実装する必要 |
| C23 | [pyuvdata](https://github.com/RadioAstronomySoftwareGroup/pyuvdata) | 部品・主候補。visibilityとメタデータの管理、UVFITS/MS/UVH5入出力 | 確認した公式対応一覧にはFITS-IDI writerはない。IDI writerとして採用しない。FITS-IDIを保つならLSLや別変換を組み合わせる |
| C24 | [python-casacore](https://github.com/casacore/python-casacore) | 部品。Measurement Setのテーブルアクセス基盤 | 単独で観測メタデータが揃うわけではなく、正しいMS構成は別途必要 |

LSLには [FITS-IDI writer](https://github.com/lwa-project/lsl/blob/main/lsl/writer/fitsidi.py) もあり、C15と組み合わせた自作相関系の出力候補になる。ソース上でvisibility、局配置、周波数、重みの受渡しを確認したが、Cas A観測網への適合とCASAでの取込みは未検証。

### 3.5 較正・画像復元・RFI処理

| ID | 候補・リンク | 利用できそうな範囲 | 注意点・採用前の確認 |
| --- | --- | --- | --- |
| C25 | [CASA：importfitsidi](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.data.importfitsidi.html)、[fringefit](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.calibration.fringefit.html)、[tclean](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.imaging.tclean.html) | 主候補。IDI→MS、残留遅延・レート、位相・振幅校正、CLEAN | 独自装置の校正方針とメタデータは必要。DiFX入力へのデジタル補正と自作相関出力の規約を混同しない |
| C26 | [AIPS](https://www.aips.nrao.edu/) | 主候補。VLBI較正と画像化の独立した代替系統 | FITLD等によるIDI取込みと装置情報・較正の設定を確認。CASAとは操作・データ管理が異なる |
| C27 | [WSClean公式マニュアル](https://wsclean.readthedocs.io/en/latest/)、[ソース](https://gitlab.com/aroffringa/wsclean) | 主候補。MSを入力とするCLEAN、multiscale等 | IDIは先にMSへ変換する。較正はCASAやDP3等の別工程と組み合わせる |
| C28 | [Difmap](https://sites.astro.caltech.edu/~tjp/citvlb/) | 代替候補。VLBIの対話的画像復元 | UVFITS経路を想定し、IDIからの変換が必要。公式案内は古く、入手・ビルド環境を別途確認 |
| C29 | [eht-imaging](https://github.com/achael/eht-imaging)、[UVFITS読込み実装](https://github.com/achael/eht-imaging/blob/main/ehtim/io/load.py) | 代替候補。RML画像復元、クロージャー量利用、模擬visibility生成 | FITS-IDI直接入力とは扱わず、UVFITS/Obsdata等へ変換。単一線形偏波・分角スケールのモデルへの適合を確認。公式READMEはpyNFFTのPython/NumPy制約を記す |
| C30 | [DP3](https://github.com/lofar-astron/DP3) | 部品・代替候補。干渉計データの前処理・較正パイプライン | 通常はMSの経路。独立時計の大きな残留遅延を解く処理の全面代替とは見なさない |
| C31 | [AOFlagger](https://aoflagger.readthedocs.io/en/latest/) | 部品。RFI検出とフラグ処理 | 観測条件に合う戦略・閾値が必要。少局・弱信号での過剰除去を確認 |

### 3.6 シミュレーション・参照値生成

| ID | 候補・リンク | 利用できそうな範囲 | 注意点・採用前の確認 |
| --- | --- | --- | --- |
| C32 | [pyuvsim](https://github.com/RadioAstronomySoftwareGroup/pyuvsim) | 主候補。天体・局・時刻・ビームからvisibilityを計算 | IQストリーム生成器ではない。点源モデルのためCas Aの拡がりは複数成分等へ離散化する。実行機能にMPI等の依存あり |
| C33 | [OSKAR](https://github.com/OxfordSKA/OSKAR) | 主候補。電波望遠鏡の模擬visibility生成 | 本来aperture array向け。使用アンテナのビーム・局モデルへの適合を確認。RTL-SDRのIQ・時計誤差・欠落をそのまま再現するものではない |
| C34 | [GALARIO](https://github.com/mtazzari/galario) | 部品。モデル画像からvisibilityを評価するCPU/GPUライブラリ | 収録・相関シミュレーターではなく、モデル比較や画像検証の参照計算に使う候補 |

CASAの [simobserve](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.simulation.simobserve.html) とeht-imagingの模擬観測もvisibility段の候補。CASAの既定ノイズモデルを独自RTL-SDRの雑音モデルと同一視しない。

## 4. 候補の組合せ

優先順位は、今回確認した機能の対応関係からの提案。採用決定ではない。

| 系統 | 想定する構成 | 長所・未確認点 |
| --- | --- | --- |
| A：標準VLBI経路 | librtlsdr系収録＋自作時刻管理 → Baseband/自作接続 → VDIF → DiFX → difx2fits → FITS-IDI → CASA → 画像 | 標準形式の経路が明確。DiFX構築と独自局設定、8 bit複素IQ、実サンプル時刻の適合が未確認 |
| B：別の実運用相関器 | 同じVDIF → SFXC → j2ms2 → MS → tConvert → FITS-IDI。画像化はMSでCASA/WSClean | DiFX以外の代替を確保。SFXC/JIVE変換環境と採用モードの適合が未確認 |
| C：小規模部品構成 | VDIF → Baseband読込み → 自作時計・遅延制御＋LSL FX → LSL IDI writer → CASA/AIPS | 各段階を追いやすい可能性。観測網向け遅延追跡・時計補正・正規化は追加実装と検証が必要 |
| D：独立した画像評価 | pyuvsim / OSKAR / CASA / eht-imaging → visibility → CASA/WSClean/eht-imaging | IQ処理の完成前に局配置と復元性能を評価できる。収録・VDIF・相関器の正しさは検証しない |

## 5. 後で試す際の確認事項

- VDIF：I/Q順序、符号・量子化レベル、複素/実数、bit深度、フレーム番号とUTCの対応、サンプルレート、欠損と無効フラグ。
- 相関：整数・小数サンプル遅延、幾何遅延、RF中心周波数を使うフリンジ回転、LO差、サンプルレート差、積分中のドリフト。
- visibility形式：UVWの単位・基線向きと複素共役、時刻尺度・積分中央時刻、周波数順序、偏波ラベル、重み、フラグ、振幅正規化。
- 単一偏波：XX等の観測量を、校正条件を確認せず完全なStokes Iとして扱わない。
- 後処理だけで修復できる範囲：相関前の大きな時計・レート誤差や長すぎる積分で失ったコヒーレンスは、後の較正で必ず回復できるわけではない。短積分や前補正・再相関の設計を検討する。
- シミュレーター：visibility参照値と模擬IQの両方を残す。時計誤差・欠落を入れた場合も正解が追える構成にする。

## 6. 状態

資料調査とメモ保存のみを実施。全候補のWSL上での動作、処理速度、ライセンスの組合せ、出力互換性は未検証。ソースの再利用範囲を決める際には各リポジトリのライセンスを確認する。次の個別指示に応じて、候補を選んで詳細調査または実装・接続試験へ進む。
