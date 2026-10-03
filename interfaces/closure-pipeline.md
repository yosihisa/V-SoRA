# VDIFからClosure＋RMLへの短区間profile

高精度の局gainや既知skyモデルを入力せず、sample時計と幾何を整列した短pilotからLO差を推定し、短積分の相対画像を作る。[学部生向け説明](../docs/guide/07-closure-rml.md)も参照。

## 入力

- session manifest：[規約](session-manifest.md)。phase_center_correction=true。4局以上のClosure amplitudeを使える連結観測網を推奨。
- sample時計モデル：[規約](clock-model.md)。実sample開始時刻・実ADC rateを測定または推定して与える。自動の未知時計復元ではない。
- 観測設定：ICRS phase center・局位置・RF・帯域・画像格子。`source.model="unknown"`なら`total_flux_jy`を省略できる。その他のsource modelはシミュレーター用で総fluxが必要。pipelineは生成skyモデルを使わない。
- 原本VDIF：8bit complex、4096sample/frame、対応した公称frame時刻。原本全体のSHA-256を計算するため長い入力には読取時間が掛かる。

## 処理

```bash
python tools/run.py vsora_correlator.closure_pipeline --manifest manifest.json --clock-model clock.json --pilot-integrations 256 --integration-s 0.3 --output outputs/analysis
```

manifestがFs2.048MHz、FFT32、blocks_per_integration=128なら短pilotは2ms、256個で0.512秒。一回の画像積分0.3秒はその有効期間に収まる。原本にはFIR/補間のguardを含める。初期start offsetの例は0.002秒。

1. sample時計・幾何delay・RFを整列したpilotをADC²で保存。
2. baseline/channelごとの未知複素値を残し、rateだけ推定する。
3. 推定rateを**入力sampleのphysical time**で補正し、幾何整列とともにIQから再相関する。
4. 各短積分・各channelでSNR10以上のClosureを抽出する。
5. 独立集合と全共分散からRMLの総相対flux1の画像を作る。

rate-only JSONはtype=`station_rate_only`。局ID/順番、UTC原点、有効時間、cadence、基準時刻、rate、入力pilotSHA-256を持つ。基準局に対する差だけで全局共通rateは測れない。既にrate補正したpilotを再推定した場合は、その適用値を加えたtotal rateを保存する。phase/amplitudeの未知定数はClosureへ残す。

単独のaligned再相関は`--rate-profile rate-only.json`を使用できる。局・原点・時間範囲を確認し、範囲外は拒否する。明示的な`--allow-rate-extrapolation`は単独CLIにあるが、pipelineは自動で外挿しない。

## 出力と失敗

`pilot/`、`rate-only.json`、`correlation/`、`closures.npz`、`rml/`、設定コピー、`summary.json`と`pipeline.json`を保存。manifest/clock/観測設定/全VDIFのSHA-256を保持。ADC²をJyとせず、RML FITSのBUNIT=1/pixel、FLUXREF=ARBITRARY、POSREF=ASSUMEDとする。

全工程完了後に`output.partial`を`output`へrenameする。例外ではpartial内にincompleteと完了した工程を残す。中止によるプロセス終了では最後の工程記録とpartialが残り、GUIは中止扱いとする。既存output/partialを上書きせず、新しい出力先で再実行する。

「工程完了」は科学的収束の判定ではない。RMLのoptimizer_success、反復上限、Closure適合、事前依存を別に読む。

## 現在の制限

整列chunkは1〜16384積分、span3秒以内、600m以下、保存するtime×channel×baselineは100万cell以下。一回のpipeline画像化は0.1〜3秒の一積分で、連続長記録処理は後続段階。別UTC原点の短露光は下記の合成入口で扱う。pilotは8時刻以上・一様cadence・3秒以内。安定sky/gain、時間Nyquist以内、使えるrate graphの連結、高SNR Gaussianを仮定する。bandpass/主ビーム差・低SNR/self-noise・RFIの実測率は未確認。

[段階023レポート](../docs/reports/023-vdif-closure-pipeline.md)に実VDIFを使う模擬試験を記録する。

## 別時刻の短露光を合成する

```bash
python tools/run.py vsora_imaging.synthesis --inputs outputs/run-a/correlation/shard-00000.npz outputs/run-b/correlation/shard-00000.npz --output outputs/synthesis
```

CLIは2〜64ファイル、GUIは2〜32ファイル。整列済みspectral NPZを使い、局ID/位置・site・位相中心・単位・周波数軸・基線順を一致させる。UTC原点を変換して時刻順に並べ、重複時刻と重なる露光を拒否する。新profileのnominal_integration_sを使い、旧profileでは最大有効露光を使うため欠損区間の全supportは証明できない。重複区間を含まない入力を選ぶ。

複素値・雑音重み・各channel・有効露光・品質診断を別々に保持し、先に複素平均しない。各局gainが露光ごとに違っても、各cellのClosureをRMLへ集める。入力SHA、rate profile SHA、除去rateと時刻原点を保存。出力はvisibility.npz、closures.npz、rml、summaryで、失敗はpartial/failure.json。

独立phase/log amplitude測定数をsummaryとGUIで表示する。amplitudeがない画像も最適化は可能だが、形状の制約が弱いことを示す。参照実装のFourier行列上限128MiB、100万baseline cell上限、時間/channel雑音独立の近似がある。連続4時間の処理性能を確認したものではない。[段階024](../docs/reports/024-vdif-synthesis.md)を参照。


## 分割相関と品質統計

整列した電圧は最大8192sample（FFTがこれより大きい場合は一FFT）ずつFXへ渡す。単位FFTの基線cross-product和、基線の有効FFT数、局powerとpower²、sample power/countを積分全体で集計する。SKとchannel flagは全体の統計から一度判定する。各ブロックのflag付き平均を先に足す方式ではない。積分結果の値・重み・露光・診断は従来の一括FXと丸め誤差の範囲で一致する。

[段階026](../docs/reports/026-bounded-fx.md)で8局1秒のVDIFを比較した。これはメモリを制限する変更で、まだ連続長記録の処理入口や3秒pilotの実装ではない。


## 3秒積分の条件

FFT32・blocks_per_integration=256ならpilot一時刻4ms。750時刻で3秒を覆い、`--pilot-integrations 750 --integration-s 3`を使える。2msなら1500時刻で3秒を覆える。時刻数とともに100万cell上限を確認する。基線rateの探索上限は時間Nyquist未満（4msなら125Hz未満）にする。原本の前後guardも必要。

幾何delayは全体3秒の中を1秒以下に分けて線形補間し、各区間中点をAstropyで再計算する。中点の基線RF位相差が0.001radを超えれば拒否する。これは参照modelの補間確認で、実EOP/局座標/大気が正確との証明ではない。rateは期間全体で一定、sky/gainは安定と仮定する。profile時間範囲外は従来通り拒否する。[段階027](../docs/reports/027-three-second-pilot.md)を参照。


## 初期LO差が大きいときのpilot刻み

画像積分とは別に`--pilot-integration-s`でpilot一回の時間を指定できる。省略時はmanifestのblocks_per_integrationを使用する。FFTの整数個で、4096sampleのVDIF frameを整数分割するか整数個含む必要がある。設定不正・時間Nyquist以上の探索・3秒超・100万cell超は原本の読取前に拒否する。

```bash
python tools/run.py vsora_correlator.closure_pipeline --manifest manifest.json --clock-model clock.json --pilot-integration-s 0.00025 --pilot-integrations 4096 --max-rate-hz 1500 --integration-s 1 --output outputs/wide-rate
```

Fs2.048MHz、FFT8なら0.25msは64 FFT。4096時刻で1.024秒、Nyquistは2000Hz。探索1500Hzは基線差の上限で、局の基準差の上限とは違う。時刻数の増加だけでは探索幅は広がらず、刻みを短くする必要がある。探索端ではpilot一セルのcoherenceはsincから約78.4%と計算される。現在の推定はこの一定減衰を未知の複素値へ含め、補正済みIQから最終積分を作る。

summary.rate_acquisitionは刻み・時刻数・span・Nyquist・探索上限・探索端coherence・SK判定可能割合を保存し、GUIも表示する。例えばmin_sk_blocks=128で64FFT/cellならSK判定割合0%。channel powerによる重みと明示的RF除外は維持するが、SKでRFIが確認できたとはしない。

**初期差がNyquist内であることは外部の条件**。周期的なsampleにより、範囲外の大きな差が小さな整合したrateに見えることがある。初期LOの測定・仕様で上限を決め、全基線を覆う刻みを選ぶ。外部上限が未確認なら「工程完了」で実機への対応を保証しない。[段階029のVDIF試験と折り返し例](../docs/reports/029-wide-rate-pilot.md)を参照。


## 原本の部分seekと検査範囲

段階031から後方の短区間はFIR/補間guardを含むframeから読み始める。公称sample0を基準にしたglobal indexを保持し、sample時計とrateを同じphysical timeで評価する。完成summaryには読取mode・範囲・各局のdecoded frame数を残す。読取中のheader/time/invalidは検査するが、飛ばしたprefixの全構造を正常と判定しない。pipelineの全原本SHA計算は維持し、長記録ではこの読取時間も掛かる。単独aligned CLIの`--sequential-input`で先頭からFIRとheader検査を行える。[時計と読取規約](clock-model.md)を参照。


## 同じ原本から複数の短windowを処理する

```bash
python tools/run.py vsora_correlator.sequence --manifest manifest.json --clock-model clock.json --window-count 3 --integration-s 0.3 --output outputs/sequence
```

配布CLIは`vsora-sequence`。2〜64window。`--step-s`を省略するとpilotのspanを開始間隔に使う。指定するならpilot/画像積分が重ならない間隔が必要。pilotはmanifestの値、または--pilot-integration-sを使う。各画像積分はそのpilot内に収め、最終積分はVDIF/FFTの整数格子に合わせる。

各windowでsample/幾何整列・rate再推定・IQ再相関を3工程で実施。高精度gain/既知skyを入力せず、windowごとの未知定数phase/amplitudeを保持する。rate profileを別windowへ暗黙に外挿しない。単一区間CLIの--correlation-onlyもこの3工程だけを保存できる。

各windowの`correlation/shard-00000.npz`を、複素平均せず最後のsynthesisへ渡す。相対RMLは最後に一度だけ実行。出力はwindow-0000/など、synthesis/、sequence.json、summary.json。window途中の失敗はcurrent_window_index、最終画像化の失敗はphase=synthesisとして区別し、全体は.partial/incompleteに残す。上書き・自動resume・弱い区間の自動skipは現段階では行わない。

window間隔・pilotが覆うstart-to-end span・画像の公称露光・baselineの有効露光を分ける。例えば2ms×256pilotの3windowではpilotspan1.536秒でも、0.3秒画像3個の露光は0.9秒。欠損やRF flagの影響は別の露光/重み/Closure数で確認する。

段階034から、原本VDIFのSHAは実行の最初に全体から一度計算し、同じ実行内のwindowだけで共有する。前回実行のcacheや任意のSHA文字列は受け取らない。manifest/clock/観測設定は小容量なので工程ごとに内容SHAも再確認する。解決済み参照先、file size、mtime_ns/ctime_ns、device/inodeを処理前後・工程間・合成後に確認し、変更を検出した場合は完成扱いにしない。単区間も同じ原本確認を行う。閉じた記録を前提にする。VDIFの全stat情報が同じに見える変更は検出を保証しない。時刻精度の限界や特別なファイルシステム操作があるため、収録中の原本を入力しない。SHAと全headerの構造検査は別である。summary.input_identityにSHA読取回数と容量、共有方式、制限を保存する。[段階034](../docs/reports/034-shared-input-identity.md)を参照。

window内の一定LO/gain、実sample時計の線形対応、初期差の探索範囲、Gaussian高SNR Closureは依然必要。window間でLOが変わることと、window内の不規則な位相揺れを復元できることは別。[段階032](../docs/reports/032-short-window-sequence.md)を参照。GUIの「区間列解析」は2〜32window。各区間の周波数差、Nyquist、SK判定可能率、使用露光、最終RMLの停止、途中失敗を表示する。[段階033](../docs/reports/033-sequence-gui.md)を参照。

## 分割rate診断（段階036）

`vsora-rate-diagnose --input pilot/shard-00000.npz --output rate-consistency.json` は、sample/幾何整列済みpilotを4分割して診断する。各部分は8時刻以上必要。`state` は `consistent` / `variation_detected` / `unverified`。局周波数差・局間共分散・UTC origin・入力SHA・差の最大規格化値を保存する。6σはFisher Gaussian独立雑音近似の診断基準で、誤検出確率の校正ではない。

単一区間・区間列CLIの `--require-rate-consistency` とGUIの対応指定は、変動検出・未判定をpilot後に停止する。初期値はfalse（診断のみ）。`rate_consistency_policy` は `report` / `required`。各子区間に `rate-consistency.json` とsummary/failureの `rate_consistency` を残す。区間列summaryは3状態の件数を集約する。失敗の `.partial` は未完了品。診断のみでは既存の一定rate推定・相関配列を変更しない。

共通rateは不定。`coherence_stability_measured=false` を常に明記する。部分内の周期的位相・alias・sky/gain変化などは平均rateだけでは識別できない。

## 滑らかな線形rateの補正

`vsora-closure-session --rate-model linear` は、4分割で測った相対局rateへ線形モデルを当てはめ、二次位相をIQへ適用してから相関する。初期値は `constant`。単一区間・区間列のCLIとGUIで選択できる。

`vsora-rate-linear --input pilot/shard-00000.npz --output rate-linear.json` は補正前LOの整列済みpilotからprofileを作る。`type=station_rate_linear`、局ID/順番、UTC origin、適用範囲、epoch `time_reference_s`、`station_rates_hz`、`station_rate_slopes_hz_per_s`、全局のrate/傾き共分散、近似model χ²を保存する。画像の正解や生成時の傾きを入力にしない。

各部分の局間共分散を使うweighted least squares。4部分とも解けること、線形モデルのreduced χ²≤3、全基線の予測endpoint rateが指定探索範囲内であることを確認する。さらに推定傾きで計算した各部分の中心化coherenceが90%以上となる範囲に限る。このcoherenceは線形モデルの計算値で、実機の相関保持率を測定した値ではない。

`correlate-aligned --rate-profile rate-linear.json` でも適用できる。基準局との差を `(rate * τ + 0.5 * slope * τ²)` cyclesとしてIQから除く。τはqueryした電圧のphysical timeからprofile epochを引いた秒。幾何補正は従来どおり。`rate_applied_slopes_hz_per_s` と `rate_profile_type` をmetadataへ残す。一定rate経路も相関数値は従来の式を使う。線形モデルの範囲外延長、補正済みLOのpilotへの重ね掛け推定は拒否する。

`--require-rate-consistency` は一定rateの整合を必須にする指定なので、線形補正との同時指定は拒否する。線形モデル自体の適合確認は常に必要。部分内の位相振動、alias、共通局rate、未知sky/gain変化は残る。モデル適合を位相安定の保証に置き換えない。

## GUI・区間列のモデル選択（段階038）

`vsora-sequence --rate-model linear` とGUIの補正モデル選択を追加した。各子区間へ `rate_model` を渡し、parent summaryへ保存する。各windowの `rate_estimate` に傾き・共分散・model適合を残す。window間のモデル補間はしない。原本SHAの共有と `.partial` の失敗位置記録は従来の規約を使う。

UI/APIは `rate_model=constant/linear` のみ受け付け、線形モデルと一定rate整合必須の同時指定を拒否する。GUIは線形選択時に対応checkboxを外して無効化する。モデル不成立・情報不足を日本語で表示し、途中品を完成画像と扱わない。結果の近似σ・χ²・計算coherenceはFisher Gaussian等の仮定付きで、実機coherenceの保証ではない。

## 線形モデルの推定誤差診断（段階040/041）

pipelineが線形モデルを選んだ場合、`rate_estimate.integration_uncertainty`とrate JSONの`integration_uncertainty`へ画像積分の条件付き診断を保存する。区間列では各windowに入る。既存記録には項目がない場合があり、GUIは未記録と表示する。相関配列・IQ補正値・重みを診断値で変更しない。

診断の`type=linear_rate_uncertainty`、`schema_version=1`。積分start/end/centerと各基線の`expected_centered_complex_coherence`、両端の位相σ、数値積分誤差、最小値を持つ。`coherence_stability_measured=false`、`hardware_confidence_calibrated=false`。mean-zero Gaussianパラメータ誤差、保存された全共分散、一様露光を仮定し、中央の一定局位相を除いた複素平均の期待値を計算する。振幅の期待値、単一実現の下限、実機保持率ではない。

CLI `vsora-rate-uncertainty --profile rate-linear.json --start-offset-s 0.002 --integration-s 3 --output diagnostic.json`は保存プロファイルへ計算だけを適用する。profile内の局ID・UTCを使い、そのプロファイル自体のSHAを保存する。このCLIの実行だけでVDIFの局ID・時刻を外部検証したことにはならない。

入力covarianceは基準局を除く順番、relative rates Hz→relative slopes Hz/sの順序。局間とrate/傾きの相関を保持し、対称・半正定値と時間coverageを確認する。窓はpilot内・3秒以内、位相分散の係数上界10000rad²まで。数値計算範囲外はエラーとなる。実データの欠損/除外mask、微小な局別query時刻の違い、速い位相揺れ・alias・誤ったcovarianceを含まない。[計算と検証](../docs/reports/040-linear-rate-uncertainty.md)、[GUI](../docs/reports/041-rate-uncertainty-gui.md)を参照。
