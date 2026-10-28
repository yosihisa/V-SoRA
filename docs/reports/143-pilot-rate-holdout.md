# 段階143：保存pilotのrate学習と未使用cell評価を分ける

- 作成日：2026-10-29
- 状態：完了（同じ原本内の条件付き比較。独立raw・fit依存・coverageの校正ではない）
- 比較元コミット：7fe1eef7bffc022f22ee3d4ba3c34b4ee9b4a74e（142）

## 読者向け概要

同じpilotで周波数差を合わせ、その同じ電圧で「よくそろった」と評価すると、合わせ方を推定した情報も評価へ入る。今回は保存済みpilotの一部でrateを推定し、その推定に使わなかったcellにも固定した補正を掛けて比較した。

4原本・各2分割の全8profileは推定できた。補正後のpower比の中央値は、学習側が未使用側より大きい分割も小さい分割もあり、各4件だった。小さい固定比較で、過学習の偏りや実機confidenceを校正した結果ではない。主比較は保存済みpilotだけを使い、原本・相関・画像を新しく生成していない。関連回帰試験が作る一時的な模擬VDIF・相関は別に実行した。

## 1. 目的・対象範囲

既存rate推定・051の受動時間診断・136の保存pilot、098/101/107の独立Gaussian評価、126の画像時刻分割をreviewした。既存の二天空識別や画像の分割を作り直さず、保存pilotのrate学習と未使用cellという未接続の比較だけを選んだ。

[検証workflow](../../workflows/pilot_rate_holdout_validation.py)から既存estimate_rate_shard、diagnose_rate_graph、diagnose_time_file、validate_rate_profileを再利用した。新しい製品API・推定法・画像尤度・GUIは追加していない。

## 2. 事前固定した分割と完了条件

132の12pilotが各原本で同じ数値であることを既存136のenrollで照合し、各high_a/high_b/weak_a/weak_bのt0.3保存pilotだけを使う。旧全pilotのrate profileは入力identityの照合にだけ読み、今回の推定や回転へは使わない。LO/sky/gain真値も渡さない。

| 学習parity（元row番号、0始まり） | 学習cell | 未使用評価cell | 事前に除く端cell |
| --- | --- | --- | --- |
| 0 | even 0〜748、375個 | odd 1〜747、374個 | odd749 |
| 1 | odd 1〜749、375個 | even 2〜748、374個 | even0 |

連続した前半/後半に分けると既存profileの時間範囲外になるため、補正の外挿を無断で許可せず、範囲内のparity分割にした。端1cellの除外は信号値を見る前に固定し、元の未trim375cell版も拒否probeとして保存した。profileのvalid_time_rangeを書き換えて広げていない。

学習は8ms間隔でNyquist62.5Hzとなり、探索上限50Hz、min_snr8/min_peak_z8/max_reduced_chisq3を固定した。初期LOが探索可能範囲内という外部仮定は残り、aliasを測って保証したわけではない。評価はDC channel4の学習/未使用×無回転/学習profile回転、計32系列。

完了条件は、全系列と失敗/未判定を保持し、source/nativeの全profile/全科学JSON・24派生NPZの全数値/metadataを一致確認すること。回転で時間powerと雑音寄与が変わらないことは確認するが、比の改善や物理的正しさを合否条件にしない。範囲外拒否・原本保持・非上書き・関連試験・公開まで確認する。

## 3. 検証結果

### 8profileと32系列

全8profileが推定でき、全32系列がconditional_estimateだった。全28基線のうち、highの採用は28、weakは19〜20だった。今回はrate取得失敗がなく、workflowのblocked/graph保存分岐を新しい実データで通したとはしない。関連する既存拒否試験と区別する。

下表は補正後の、各集合で有限な比だけの中央値とnull数。比は雑音差引MEAN POWER/TIME POWERの無制限比で、振幅保持率や物理coherenceではない。

| 原本 | 学習parity | 採用基線 | 学習：中央値 / null | 未使用：中央値 / null |
| --- | ---: | ---: | ---: | ---: |
| high_a | 0 | 28 | 1.006740 / 1 | 0.994705 / 0 |
| high_a | 1 | 28 | 0.993504 / 0 | 1.006452 / 1 |
| high_b | 0 | 28 | 1.000268 / 1 | 0.997366 / 1 |
| high_b | 1 | 28 | 0.997400 / 1 | 1.000260 / 1 |
| weak_a | 0 | 20 | 1.083876 / 6 | 0.914544 / 6 |
| weak_a | 1 | 19 | 0.931268 / 6 | 1.081418 / 6 |
| weak_b | 0 | 20 | 0.972996 / 3 | 1.174407 / 2 |
| weak_b | 1 | 20 | 1.211221 / 2 | 0.972543 / 3 |

各集合で比が有限となる基線は異なり得るため、中央値の差は同じ支持の対検定でも信頼区間でもない。8foldで学習側が大4/小4という記述を、独立8試行の成功率や系統的偏りの有無へ換算しない。同じrawの逆foldは独立な観測ではない。

全32×28=896行で、比null80、負237、1超201をそのまま保存した。回転前後の時間power・推定雑音寄与は、相対2e−12＋最大raw時間powerの1e−11を絶対許容として一致。変化したmean power/比を物理的な相関回復量にしない。4ms cell中心の回転はcell内の平均化損失を戻さない。

### 範囲・再現・所属

全8profileで、未trim側の端cellは既存validate_rate_profileの範囲外として拒否された。high_a/parity0は実time_file APIと導入CLIでも拒否され、診断出力は作られなかった。先に固定した374cellは範囲内で処理できた。これはprofile範囲の契約を守る確認で、未使用cellの統計的独立性を証明するものではない。

sourceの実APIと、checkout外nativeの既存rate/time_scatter CLIで、全科学JSON・全8profile・24派生NPZの312数値配列/全metadataが完全一致した。nativeの実41 CLI起動すべてで、runpyを通した通常の引数解析と処理を実行し、finallyで実際に読み込んだ製品moduleの導入prefixを確認した。nativeはrunner/PYTHONPATHなしで、wrapper自身はcheckoutが必要である。

元raw76、保存pilot12・旧profile4のSHAを保持し、派生NPZには親SHAと元row番号を対応させた。派生metadataは単位・時計・時刻・FFT数を保持しており、原本を更新していない。全study出力の非上書きを両環境で確認した。

### 試験・有限時間・引用した正式基準

既存rate/rate_graph/time_scatter対象はsource76成功4.40秒、導入76成功3.32秒、各640警告/除外0。新unitなし。正式検証中はcode/試験/tool/workflow448件を凍結し、初回の正式手順で完了した。

所有runnerの起動から終了までsource21.73秒、native32.45秒。起動/import・入力照合・派生保存・API/CLIを含み、nativeは各CLI起動も含む。各操作の内訳を別記録に保存した。出力はsource86.59MiB、native86.74MiBで128MiB上限内。今回peakRSSは測っていない。cache制御・全夜/GPU/最低PCの性能確認ではない。

製品103file＋4assetは138 wheel/source/導入先と全byte一致。新full/collect/wheel/導入/browserは実施していない。[138正式記録](../../validation/runs/stage138/verification.json)の両全2321成功542.82/541.45秒・各30220警告/除外0と、両実GUI28worker/56downloadを引用し、143の新合格件数へ加算しない。通常GUI8765も変更していない。

[全profile・全系列と入力識別](../../validation/runs/stage143/reference.json)、[正式検証](../../validation/runs/stage143/verification.json)、[時間・容量](../../validation/runs/stage143/measurements.json)、[再実行条件](../../validation/runs/stage143/README.md)を保存した。公開監査指摘0、文書リンク1879件で欠落0。

## 4. 制約・未解決事項

未使用cellでも同じraw・有限周期・filter境界・clock/gainを共有する。学習profileが未使用の数値を直接読まないことと、無条件に独立な電圧から作った推定であることは別である。既存051の独立cell/固定回転という仮定を、この分割だけで実証したことにはならない。

同pilot推定依存・SNR選別・実FFT独立性・coverageは未校正。実Cas A、未知gain/SEFD/beam、低SNR画像尤度、全夜/GPUも未検証のまま。今回の比やrateの公称共分散をRMLの誤差補正へ自動適用しない。

## 5. 次段階

144はSNR選別の条件付けを既存047と独立評価APIに照らして点検し、既存機能や今回のparity比較と重複しない最小対照へ目的を固定する。150で文書整理と専用根本レビュー。期限2026-11-06 15:00JST、追加reset禁止を維持する。
