# 段階132：独立4原本の未知LO取得と短積分相関

- 作成日：2026-10-27
- 状態：完了（固定4原本の取得・補正相関・Closure検証。画像性能は未評価）
- 比較元コミット：f78a36391d161ae09c6f0b42d40084d0a82b3cf9（131）

## 読者向け概要

131で作った模擬電圧を、天空の形と局の周波数差を知らない観測入力として処理した。SEFD（雑音を天空fluxに換算した感度の尺度）1000/10000Jyの仮定を各2seed、4原本とし、最終積分0.3・1・3秒の12条件を固定した。電圧は再生成せず、原本SHAで同一性を確認した。

相関とは2局の電圧の複素積を平均する処理である。周波数差が残ると位相が回り、平均が打ち消し合う。そこで先に4msずつ750個、計3秒のpilotから局の相対周波数差を推定し、その推定だけで最終の短い相関を補正した。0.3秒の最終相関も取得に3秒を使い、0.3秒だけで全てを完了したわけではない。

今回の4原本で相関まで完了したのは12条件、取得停止は0条件だった。Closureの個数を記録したが、画像の形が復元できたという結果ではない。

## 1. 目的・対象範囲

1.42GHz、最大600m、8局、3.04秒、2.048MS/s・8bit I/Qの131原本4件を読み、未知LO（局の発振器の相対周波数差）を取得できるか、補正後に画像化用の制約が残るかを確認する。既存の相関器・rate推定・Closureを変更せず使う。

Closure phaseは三角形の位相和phi_ij+phi_jk-phi_ikで、局ごとの位相が相殺される。振幅Closureも四局のlog振幅を和差にし、局ごとの一定gainを相殺する。しかし積分中に周波数差で情報を失う問題を自動的に解くものではない。今回の順序は「周波数差推定→電圧側で補正→平均→Closure」である。

画像復元、真値LOによる救済、閾値の調整、新しい低SNR尤度、零天空、実機は対象外。対象試験に含む既存の小さな4局fixtureでは従来のRMLを回帰するが、今回の4原本からは画像を作っていない。

## 2. 完了条件

公開131/referenceの全76入力SHA、unknown model/fluxなし/noise.enabled=Trueを確認する。pilot750×4ms、開始0.002秒、検索100Hz、一定rate、部分pilot診断はreportの既定動作、最終0.3/1/3秒、Closure baseline SNR10を先に固定した。

sourceとcheckout外の導入済みnative CLIで12条件ずつ実行し、全pilot・相関・Closure保存数値、graph、局rate、部分pilot診断、取得設定、全科学JSONを照合する。既知の非連結/不整合だけを記録し、予期しない例外は停止する。全条件とstudyの既存出力拒否、原本保持、prefix、既存core/wheelの不変、対象試験、レポート・監査・匿名公開までを条件とした。

## 3. 実際に行った作業

`workflows/short_integration_matrix.py`に固定行列、原本の照合、相関の実行、診断集計を追加した。sourceはtools/run.pyから既存相関CLIを起動し、内部の公開process_closure_session APIを通した。導入側は一時作業フォルダからpython -mの既存native CLIを実行し、runnerとPYTHONPATHを使わない。外側の検証helperは同じcheckoutにあり、wheelだけで使える新製品機能とは主張しない。

同じ原本の3条件では、pilot全数値・graph・推定rate・部分pilot診断の一致も確認した。真値rateは推定を終えてから、基準局ST01に対する誤差と一定誤差の箱型平均保持率だけに使った。推定に渡す引数はmanifest/clockで、入力外の生成rateや天空を渡していない。観測config.seed=42はschema残存値で、実生成seedは131の記録にある。

Closureを全て列挙すると基線の共有により重複するため、各セルの独立行と共分散を既存QR処理で選び、rankも集計した。ここでの「独立」は同じセルの線形制約の意味であり、周波数セルやFFT標本の統計的独立性を実証した意味ではない。

変更ファイルは上記workflow、新しい対象試験、導入照合tool、本レポートと索引、validation/runs/stage132の4記録である。既存production/package、既定画像格子、係数、GUIは変更していない。

## 4. 検証条件・結果

### 未知LOの取得

| 原本 | 採用基線 | graph | 部分pilot診断 | 相対局rate最大誤差 Hz |
| --- | ---: | --- | --- | ---: |
| high_a | 28 / 28 | connected | consistent | 0.00065409 |
| high_b | 28 / 28 | connected | consistent | 0.00075469 |
| weak_a | 22 / 28 | connected | unverified | 0.00896083 |
| weak_b | 22 / 28 | connected | unverified | 0.00407091 |

graphが連結でも局rateの整合性や実coherenceの保証にはならない。部分pilot診断は既定のreportで保存し、consistentを強制していない。unverifiedを成功に書き換えない。

### 最終積分と有効な制約

| 原本 | 積分秒 | 相関処理状態 | 取得停止理由 | 全位相/振幅Closure | 独立位相/振幅rank | 計算上の最小保持率 |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| high_a | 0.3 | complete | なし | 78/130 | 43/40 | 0.99999979 |
| high_a | 1 | complete | なし | 116/246 | 53/50 | 0.99999766 |
| high_a | 3 | complete | なし | 156/378 | 61/58 | 0.99997896 |
| high_b | 0.3 | complete | なし | 75/126 | 42/39 | 0.99999985 |
| high_b | 1 | complete | なし | 120/258 | 54/51 | 0.99999830 |
| high_b | 3 | complete | なし | 156/378 | 61/58 | 0.99998472 |
| weak_a | 0.3 | complete | なし | 0/0 | 0/0 | 0.99997239 |
| weak_a | 1 | complete | なし | 4/0 | 4/0 | 0.99969320 |
| weak_a | 3 | complete | なし | 23/20 | 20/15 | 0.99724082 |
| weak_b | 0.3 | complete | なし | 0/0 | 0/0 | 0.99999313 |
| weak_b | 1 | complete | なし | 3/0 | 3/0 | 0.99992366 |
| weak_b | 3 | complete | なし | 19/16 | 19/13 | 0.99931304 |

SEFD1000Jyの2原本では最終積分を延ばすと制約数が増えた。一方、SEFD10000Jyの2原本は0.3秒で位相/振幅とも0、1秒でも少数の位相制約だけだった。これは固定条件の結果であり、短積分一般の失敗率や実RTL-SDRの感度限界ではない。長いpilotから周波数差を取得できることと、短い相関に画像用の情報が残ることは別である。

保持率は取得rateの真値誤差からabs(sinc(delta_rate*T))を計算した値で、一定の基線rate誤差だけを仮定する。実測coherence、実OCXO安定性、画質や誤差区間ではない。

未相関はclosures=nullの「未評価」、相関後に使えるClosureが無い場合は有効数/rank=0として保存する。これらを同じ0点にしない。今回の条件の結果は[全科学記録](../../validation/runs/stage132/reference.json)で確認できる。

### 再現・入力保持・試験

正式50対象（新11＋既存39）がsource26.15秒、導入24.03秒で成功した。各2280既存Baseband/NumPy警告、除外0。新試験は原本改変/余分なfile/順序/真値混入/metadata拒否、正確な科学的停止、未知の例外の停止、nullと0、共有基線のrankを確認する。最初の50件の予備実行は正式数へ加算していない。両2263は収集のみで、全2263は実行していない。

source/導入の全12条件の科学JSONが一致した。pilot 156配列、最終相関 156配列、Closure 180配列、計492配列を実値・dtype・shape・SHAで直接比較した。complete pipelineのrate/部分pilot/acquisitionや相関summary、spectral科学metadataも含む。元入力のSHAと出力依存のarchive/profile SHAは科学同一比較から分け、原本全SHAと適用profileのSHA対応を各環境で別に確認した。NPZ全archive byteの同一性は主張しない。

全12条件の再出力拒否、source/導入study全体の再出力拒否、原本全76SHAを確認した。source親processの科学module 9個の正確な位置と、導入親processの9個のprefixを検査し、native CLIは同じ導入Python・checkout外・PYTHONPATHなしで起動した。全CLIの内部moduleを個別列挙したという主張ではない。既存wheelの全package fileについても導入先とsourceのbyteを照合した。

凍結432file、既存core/package215file、環境pip freeze、既存121wheel103file＋4assetは不変。新wheel・GUIブラウザ・全回帰は再実行していない。最新全回帰121の両2116成功（609.28/607.50秒、各27396既存警告、除外0）を引用する。通常GUIは導入済み121のまま維持した。

出力はsource 91301091byte、導入 91301343byteで、各512MiB上限内。各CLIは180秒・環境ごとの正式処理は1200秒の上限を設けた。時間は[計測記録](../../validation/runs/stage132/measurements.json)に保存した有限実行値で、最低PC仕様や全夜/GPUのbenchmarkではない。

公開監査指摘0、文書リンク1723件で欠落0。[検証記録の入口](../../validation/runs/stage132/README.md)から条件・再現確認をたどれる。

## 5. 制約・未解決事項

同じ原本内でpilot・最終積分・3積分条件が重なる。4固定原本を2環境で処理しても24独立観測ではなく、成功率・false-alarm率・coverageを推定する試行ではない。生成seedはnoise/gain/LOを同時に変えるため、雑音だけやSEFDだけの因果介入でもない。

仮定SEFD1000/10000JyとCas A flux1000Jy、正確なsample clock/decoder scale、一定gain/LO、単一epoch、131の帯域制限/量子化モデルを継承する。高SNR Closureとweak-source重みは既存近似で、source self-noise・filtered FFT相関を十分に扱った尤度ではない。有効制約が残ることを、画像の正確さや較正の完了へ読み替えない。

実RTL-SDR/OCXOのCas A、実SEFD、弱実信号の未知LO/gain、実FFT独立性、低SNR画像尤度、全夜/GPU性能、Windows収録は未検証または対象外を維持する。

## 6. 次段階

133候補で今回の保存相関を画像段階へ渡す。新しい原本や相関を増やさず、処理完了・選択run収束・形状差を分離する。truthで初期値や係数を選ばず、必要なfit量と残量を確認して正式範囲を固定する。今回のClosure数を画像化成功として扱わない。文書整理140、根本見直し150、期限2026-11-06 15時を維持する。
