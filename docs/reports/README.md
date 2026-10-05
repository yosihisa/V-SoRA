# 開発段階レポート

開発段階ごとに目的、実際の作業、検証結果、未解決事項を記録し、その段階の変更と一緒にコミットする。

| 段階 | レポート | 状態 |
| --- | --- | --- |
| 000 | [初期整理・開発構想](000-initial-plan.md) | 調査・設計の初期記録。ソフト実装と動作検証は未実施 |
| 001 | [共通入力・参照画像](001-foundation.md) | 12件の検証成功。ソフト別構成へ移行 |
| 002 | [理想visibility・画像復元](002-ideal-imaging.md) | 22件成功。点源・2点源の解析比較とFITS画像出力 |
| 003 | [Cas A・局配置比較](003-casa-array-study.md) | 24件成功。7条件を比較、リング配置はCLEAN非収束 |
| 004 | [VDIF・FX相関](004-vdif-fx.md) | 30件成功。短時間IQの量子化・遅延・相関を検証 |
| 005 | [IQから画像まで](005-iq-to-image.md) | 33件成功。8局・16snapshotをVDIF→IDI候補→画像へ接続 |
| 006 | [CASA独立互換確認](006-casa-compatibility.md) | 33件成功。共役を修正、偏心点源の位置・振幅と重みを確認 |
| 007 | [未知の局応答の較正](007-fringe-calibration.md) | 39件成功。5seedで別Cas A観測のvisibility誤差0.9～1.2% |
| 008 | [IQの未知LO差と再相関](008-iq-fringe-tracking.md) | 44件成功。2passで平均visibility誤差0.60%、VDIF frame iterator |
| 009 | [ADC時計・分数sample整列](009-adc-clock-alignment.md) | 48件成功。連続解析波形で時計推定・補間・幾何の符号を検証 |
| 010 | [session・相関CLI](010-session-cli.md) | 52件成功。ADC→2pass較正→Jy/IDI→画像、stream/shard保存 |
| 011 | [独立環境・wheel導入](011-reproducible-environment.md) | 独立venvで52件成功。checkout外の参照画像・CLI実行を確認 |
| 012 | [Cas Aモデル較正](012-casa-model-calibration.md) | 55件成功。spanning tree、2感度条件の16snapshot、prior依存を明示 |
| 013 | [多channel IDI・正確なCLEAN](013-spectral-idi-exact-clean.md) | 57件成功。CASA8channel、偏心点源の発散を修正して66回で収束 |
| 014 | [時計・幾何sample整列](014-stream-clock-geometry.md) | 58件成功。VDIFのclock/RF補正、buffer8197sample、EOF拒否 |

| 015 | [短いpilot積分・入力検査](015-short-pilot-input-validation.md) | 68件成功。1ms積分・設定誤字・FITS溢れを検査 |

| 016 | [実データ用CASAアダプター](016-casa-production-adapter.md) | 71件成功。actual FITSのchannel重み・flagをMSへ保持 |

| 017 | [周波数別重み・RFI診断](017-spectral-quality-rfi.md) | 80件成功。模擬RFI誤差996%→4.77%、有限雑音試験の誤flag0 |

| 018 | [学部生向け文書](018-undergraduate-documentation.md) | 原理・用語・結果の意味を整理。リンク切れ0、点源手順を再実行 |

| 019 | [日本語ブラウザGUI](019-japanese-browser-gui.md) | 90件成功。Chromium実操作・日本語font・画像表示・中止・wheelを確認 |

| 020 | [Closure・短積分の周波数差](020-closure-short-integration.md) | 98件成功。局利得不変性、独立共分散、0.3秒IQのLO損失と補正 |

| 021 | [Closure＋RML・日本語GUI](021-closure-rml-reference.md) | 105件成功。相対flux、未知局利得、短露光・事前依存、Cas A上限到達を記録 |

| 022 | [モデル不要のLO差推定](022-model-free-rate.md) | 111件成功。未知sky/gain、短pilot、3seedのIQ補正後Closure、欠損graph |

| 023 | [VDIFからClosure＋RML・解析GUI](023-vdif-closure-pipeline.md) | source/wheel115件成功。未知flux、sample/幾何/rate、partial、checkout外CLI/GUI |

| 024 | [短露光VDIF合成・感度不足](024-vdif-synthesis.md) | source/wheel121件成功。8局Cas A高感度仮定で形状誤差2.8%、低感度失敗とRML上限を記録 |

| 025 | [短積分の感度計画](025-sensitivity-planning.md) | source125件成功。32期待値条件・アンテナ換算・日本語感度GUI。実機感度は未測定 |

| 026 | [相関の分割処理](026-bounded-fx.md) | source/wheel129件成功。8局1秒の統計を保持し、peak RSS約1.42GiB→325MiB |

| 027 | [3秒pilot・分割幾何](027-three-second-pilot.md) | source130件成功。4局3秒VDIFとGUI、rate誤差0.0015Hz。実OCXO安定時間は未測定 |

| 028 | [Cas Aの3秒合成・低感度](028-casa-three-second-sensitivity.md) | source130件成功。8時刻処理完了、形状誤差34〜37%で画像の良好復元は未確認 |

| 029 | [短い刻みの広範囲LO探索](029-wide-rate-pilot.md) | source/wheel140件成功。1185Hz基線差をVDIFから補正、SK未判定と検出不能aliasを記録 |

| 030 | [全成分を保持した位置合わせ評価](030-full-support-registration.md) | source/wheel151件成功。固定Cas A画像の高感度2.36%、低感度35〜39%。復元画像は変更せず |

| 031 | [guard付きVDIF部分読取](031-guarded-vdif-seek.md) | source/wheel157件成功。後方区間の相関差0、decoded frame1402→152。未読prefixの範囲を明示 |

| 032 | [短window列・LO再推定](032-short-window-sequence.md) | source/wheel162件成功。同一VDIFの3区間でLO差変化を推定、露光0.9秒。選択RMLは800反復上限 |

| 033 | [短区間列の日本語解析GUI](033-sequence-gui.md) | source/wheel169件成功。3区間解析・入力不足・中止を実ブラウザで確認、RML上限を表示 |

| 034 | [固定原本の識別情報共有](034-shared-input-identity.md) | source/wheel181件成功。全原本SHA読取12→4回、相関配列差0。JSON内容確認とVDIF stat検出限界を記録 |

| 035 | [積分中の周波数変動とClosure](035-within-window-rate-drift.md) | source/wheel192件成功。中程度3秒は処理完了でも減衰・Closure偏り。強い変動は3秒停止、0.3秒で減衰縮小 |

| 036 | [pilot内の分割rate診断](036-subpilot-rate-diagnostics.md) | source/wheel204件成功。4分割と必須停止をCLI/実GUIで確認。周期位相の見逃し・未判定を記録 |

| 037 | [測定した線形rateのIQ補正](037-measured-linear-rate-correction.md) | source/wheel211件成功。4部分から推定した傾きで3秒相関、模擬点源の最小対照振幅比99.93%。実機・Cas A画像は未検証 |

| 038 | [線形rateの日本語GUIと区間列](038-linear-rate-gui-sequence.md) | source/wheel216件成功。実GUIで選択・傾きσ・3区間RML・未判定停止。独立CLIの合成配列差0 |

| 039 | [周期位相を加えたVDIFとClosure](039-periodic-phase-coherence.md) | source/wheel225件成功。実GUI/CLIでも分割整合・線形採用のまま約15%減衰。遅い周期は不整合停止 |

| 040 | [線形rateの推定誤差診断](040-linear-rate-uncertainty.md) | source/wheel249件成功。全共分散・Gaussian65536標本・CLI一致。99.98%の条件付き予測でも周期位相の対照比84.59%、実機保証なし |

| 041 | [推定誤差診断の日本語GUI](041-rate-uncertainty-gui.md) | source/wheel250件成功。実Chromiumで単区間・3区間・周期位相・Gaussian表を確認、日本語/390px・JS/外部通信0。RMLは100反復上限 |

| 042 | [rate推定の誤差共分散検証](042-rate-covariance-validation.md) | source/wheel269件成功。Gaussian電圧モーメント・8条件×1024試行。公称95%領域内79〜100%、近似σの限界と未採用例を記録 |

| 043 | [rate共分散検証の日本語GUI](043-rate-covariance-gui.md) | source/wheel270件成功。実Chromiumで8条件×1024試行、採用率と選別後の誤差統計を表示。日本語/390px・JS/外部通信0 |

| 044 | [共有信号を含むClosureの誤差伝播](044-joint-closure-noise.md) | source/wheel297件成功。全実共分散・phase/log amplitude交差・局gain不変性・8条件×16384標本。一次近似との差と特異極限を記録 |

| 045 | [Closure雑音検証の日本語GUI](045-closure-noise-gui.md) | source/wheel298件成功。実Chromiumで8条件×16384試行、電圧標本と相関値近似・分散比を区別。日本語/390px・JS/外部通信0 |

| 046 | [局の標本からvisibility雑音を推定](046-sample-noise-estimator.md) | source/wheel325件成功。真値不要の有限標本補正、4条件×32768試行の平均・半正定値・局gain変換を確認。実FFT独立性・信頼区間は未校正 |

| 047 | [相関ファイルの雑音診断](047-observation-noise-diagnostic.md) | Gaussian IQ→FFT・条件付き一cell CLI・固定VDIFの既存12配列差0。source/wheel355件成功。実FFT独立性・信頼区間・実機は未検証 |

| 048 | [保存相関の雑音診断GUI](048-observation-noise-gui.md) | source/wheel365件成功。実Chromiumで軸選択・4状態fixture・低SNR無効行・JSON保存、日本語/390px・JS/外部通信0 |

| 049 | [FIR・補間後のFFT雑音](049-filtered-fft-noise.md) | source/wheel400件成功。既知Gaussian6条件×8192試行、時刻差と局別係数の全共分散、モデル換算数。実測独立数・実機は未確認 |

| 050 | [FFT雑音検証の日本語GUI](050-filtered-noise-gui.md) | source/wheel401件成功。実Chromiumで6条件×8192試行、モデル換算数と全共分散差を表示、日本語/390px・JS/外部通信0 |

| 051 | [pilot時間散乱の条件付き診断](051-pilot-time-scatter.md) | source/wheel433件成功。Gaussian4条件×2048試行、固定VDIFの対照比約0.985〜1.031・高速変動最小約0.726。実機信頼区間・coherenceは未測定 |

| 052 | [pilot時間散乱の日本語GUI](052-pilot-time-scatter-gui.md) | source/wheel447件成功。実Chromiumで対照・高速・旧/信号不足fixture、RF・profile・二重補正・JSON、日本語/390px。既存一cell GUIも回帰 |

| 053 | [異標本bispectrumの試作](053-distinct-sample-bispectrum.md) | source/wheel483件成功。全組合せ・Gaussian5条件×16384試行で共通標本の偏りとU₃の平均を確認。非常に弱い信号は未分解、実機・RML未適用 |

| 054 | [三次統計検証の日本語GUI](054-bispectrum-validation-gui.md) | source/wheel484件成功。実Chromiumで5条件×16384試行、偏り・U₃平均・弱い真値の未分解、日本語/390px・JS/外部通信0 |

| 055 | [時間相関と三基線積](055-temporal-bispectrum.md) | source/wheel511件成功。既知ゼロ源5条件×8192試行、残留偏りと128→15/26の間引き損失。実機独立性・感度は未確認 |

| 056 | [時間相関の日本語検証GUI](056-temporal-bispectrum-gui.md) | source/wheel512件成功。実Chromiumで5条件×8192試行、残留偏り・保持数・モデル条件、日本語/390px・JS/外部通信0 |

| 057 | [三基線積の雑音と条件付き感度](057-bispectrum-sensitivity.md) | source/wheel539件成功。ゼロ源分散の添字列挙・Gaussian5条件、短積分/間引きの32仮定計算。実機感度・検出確率・画像は未確認 |

| 058 | [三基線積の短積分比較GUI](058-bispectrum-sensitivity-gui.md) | source/wheel540件成功。実Chromiumで5分散・32仮定行の全数値、日本語/390px・JS/外部通信0。実機観測時間は未計算 |

| 059 | [天体信号を含む三基線積の全共分散](059-joint-bispectrum-moments.md) | source/wheel571件成功。独立添字列挙・Gaussian5条件×8192試行で共有三角形の全実共分散。実機・非Gaussian尤度・画像は未確認 |

| 060 | [三角形間の誤差相関の日本語GUI](060-joint-bispectrum-gui.md) | source/wheel572件成功。実Chromiumで5条件の全表示値・図の説明、日本語/390px・JS/外部通信0。RML未適用 |

| 061 | [三次統計の追加の和の蓄積](061-streaming-bispectrum-sums.md) | 最終source/wheel610件成功。chunk FFTとバッチU₃の差約10⁻¹⁷。初回installedの状態API競合を再現修正、実区間列ブラウザで完了・失敗・中止 |

| 062 | [三次統計の保存形式と元相関の照合](062-bispectrum-sidecar-format.md) | source/wheel669件成功。raw配列の完全読戻し・U₃再計算・元相関との識別と必要な整合性。実VDIFの経路・実機・RML未適用 |

| 063 | [相関器のFFTから三次統計を収集](063-fx-bispectrum-accumulation.md) | source/wheel688件成功。0.1秒合成IQで既存7/12配列差0、局別欠損の共通U₃とバッチ一致。実VDIFの経路は次段階 |

| 064 | [VDIF相関から三次統計を保存](064-vdif-bispectrum-sidecar.md) | source/wheel704件成功。実合成VDIFのFIR・補間・幾何補正後のU₃、元13配列・metadata差0。欠損/RF/仰角、導入済みCLIと元相関照合 |

| 065 | [三次統計の保存を指定する日本語GUI](065-bispectrum-storage-gui.md) | source/wheel723件成功。相関13配列・相対画像差0。実Chromiumで単一/区間列の全保存値・ダウンロード照合、日本語/390px・失敗/中止。初回の表selectorを修正 |

| 066 | [保存した三次統計を時刻と周波数で確認](066-bispectrum-inspection.md) | source/wheel743件成功。保存VDIFの利用可・マスクcell、M0/1/2のnull、原本照合・変更・上書き拒否、checkout外CLI一致。雑音・RML未適用 |

| 067 | [保存三次統計の日本語GUI](067-bispectrum-inspection-gui.md) | 最終source/wheel761件成功。実Chromiumの全値・履歴の二入力・M0/1/2・マスク・JSON・日本語/390px。初回touchの時刻が変わらないテストを修正、基準は維持 |

| 068 | [短積分U₃を平均した分布の確認](068-bispectrum-window-averaging.md) | source/wheel799件成功。5既知モデル×Q4条件各8,192反復、全共分散1/Q・Gaussian対照一致。弱い源はQ64でも公称包含率と差が残り、Gaussian尤度を保証しない |

| 069 | [短積分平均の誤差分布を日本語GUIで確認](069-bispectrum-averaging-gui.md) | source/wheel801件成功。実workerの20条件が068と完全一致、両実Chromiumで全数値・JSON・図説明・日本語/390pxを確認。包含率の差を処理失敗と混同しない |

| 070 | [未知の局gainとbispectrum平均の振幅制約](070-bispectrum-gain-constraints.md) | source/wheel825件成功。有理数rank照合、4局の平均振幅制約0対従来2、8局の48行中非自明20。正定値反例は局power・有限標本共分散が異なり、全分布・画像化不能の主張に使わない |

| 071 | [未知gainと母平均の制約を日本語GUIで確認](071-bispectrum-gain-gui.md) | source/wheel827件成功。実workerと両実Chromiumで6局数・4局の例の全数値・JSON・日本語/390px・図説明を確認。母平均rankを雑音rankや画像化の可否に使わない |

新しいレポートは [テンプレート](templates/stage-report.md) を使用する。段階の対象コミットは、そのレポートを追加・更新したGit履歴から確認できる。
