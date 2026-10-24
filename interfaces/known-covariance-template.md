# 既知点源／Cas AのGaussian共分散による比較

段階101。`vsora_simulator.gaussian_template_validation` が、[段階100の既知Gaussian API](known-covariance-gaussian.md)と既存の同梱天空・配置をつなぐ。

## 前提と固定条件

8局、1.42GHz、最大600m、単一時刻の固定幾何を使う。点源とCas Aの天空テンプレートは零対照を除いて総flux1000Jyに正規化する。Cas Aの入力画像は形状代理であり、実際の1.42GHzのflux・主ビーム・偏波の測定ではない。

候補共分散C0=点源、C1=Cas Aと受信機SEFD・局位相基準・電力をすべて与える。proper complex Gaussianの全局共通電圧を直接生成し、各windowの全M標本からSを作る。既存三角形のraw profileからSを組み立てず、Wishart近道も使わない。独立標本数Mは仮定であり、実FFT/FIR/ADCの独立性を検証しない。

| 条件 | M | 仮定SEFD | 点源生成SEFD | Cas A生成SEFD | 天空 |
|---|---:|---:|---:|---:|---|
| g00〜g02 | 512 | 1000／10000／585966… | 仮定と同じ | 仮定と同じ | 点源対Cas A |
| g03〜g05 | 19200 | 1000／10000／585966… | 仮定と同じ | 仮定と同じ | 点源対Cas A |
| g06 | 19200 | 1000 | 10000 | 1000 | 受信機誤指定 |
| g07 | 19200 | 10000 | 1000 | 10000 | 受信機誤指定 |
| g08 | 512 | 1000 | 1000 | 1000 | 両候補とも零天空 |

SEFDの単位はJy。585965.634733…Jyは、既存APIによる直径1m・100K・効率0.6の計算例で実測値ではない。g06/g07は片方の生成雑音を意図的に変更した人工対照で、天体形状によって実受信機の状態が変わると仮定するものではない。

各label512独立window、計9216window。seedは101000〜101008、SeedSequence `[seed,role]` のrole0=点源、1=Cas A。既知gainの照合は別stream `[seed,role,99]`。生成batchの一配列は100万complex values以下。smokeではg00/g06/g08をM16・各16window・別seedへ変更し、正式MC精度の結果とは区別する。

## APIとCLI

```python
from vsora_simulator import gaussian_template_validation as study
plan = study.case_plan('full')
result = study.experiment(plan[0])
summary = study.run('outputs/known-covariance-new', profile='full')
```

`experiment` は変更していない固定caseのみを受け付ける。boolと数値を含めてJSON表現が固定planと一致することを要求する。`run` は既存出力を上書きしない。不正profileは出力を作る前に拒否する。計算・照合の例外は伝播し、成功summaryを作らない。

```bash
# ソース版
python tools/run.py vsora_simulator.gaussian_template_validation --profile full --output outputs/reference-new
# wheel導入後。checkout外からも使用できる。
python -m vsora_simulator.gaussian_template_validation --profile full --output reference-new
```

返すsummaryのtypeは `known_covariance_template_discrimination`。候補・生成共分散の実部/虚部、全windowの対数尤度比、誤り率と区間、AUROC、seed、既知gain/直接電圧の照合結果、同梱設定と天空画像のSHA256を含む。各case JSON・summary JSON・科学図を保存する。`progress(i,total,case_id)` のcallbackも利用できる。

## 判定と統計量

各windowのscoreは `log L(C1)−log L(C0)`。score>0をCas A、score<=0を点源に固定する。学習を行わず、評価データで閾値やモデルを選ばない。等しい候補はscoreが厳密0となり、同点を点源とするためg08の正答率は0.5になる。

balanced accuracyは二labelの正答率の等重み平均、AUROCは点源scoreとCas A scoreの順位の指標。同点は半分として数える。全512²対は独立ではなく、AUROCの二項試行数として使わない。

誤り率の個別Clopper-Pearson95%区間は、固定した候補・生成分布・閾値の下での独立windowに対する区間。`known_model_error_summary(k,n)` が返し、`conditional_fixed_models_binomial_confidence_level` で条件を示す。学習の揺らぎ・全条件同時の保証・画像の信頼区間を表さない。誤り0でも未知条件でのリスク0を証明しない。

各label先頭2windowのscoreを、Sを使わない電圧の直接二次形式と照合する。同じwindowについて既知の局gainを電圧と両候補へ与え、尤度比と判定が保たれることも照合する。これは未知gainを推定した試験ではない。

`expected_log_likelihood_ratio_per_window` は、生成母共分散をSへ入れたときの期待score。M個の観測標本から母共分散を測った値ではない。Mに対する線形性から求めたGaussianモデル内の計算値であり、実機の成否を判定するものではない。

## 適用範囲

この尤度は局位相基準と電力も利用する。天空位置・位相基準まで与えた二候補の識別で、未知位相で位置の自由度も残るClosureの画像復元とは条件が異なる。既存U3識別器と数値を比べるときは、学習の有無、入力情報、受信機の既知性、異なる乱数実現値を区別し、対応のある比較やClosureの限界と解釈しない。

未知gain/SEFD/LOの推定、量子化、実効M、実機データ、低SNRのClosure画像尤度、現在のRML、全夜/GPU性能は今回の対象外。段階101では日本語GUIを分け、後続の段階102で同じfull条件をGUIへ接続した。

正式結果は [段階101レポート](../docs/reports/101-known-covariance-template.md) を参照。

## 日本語GUI（段階102）

「動作検証」→「既知共分散で点源/Cas Aを比較」で固定9条件を実行する。概要9行と、選んだ条件の1024区間を表示する。runnerのないworkspaceからも同梱API/assetsを使う。全scoreと共分散は実downloadのsummary/case JSONに残す。詳しくは [操作ガイド](../docs/guide/06-gui.md) と [段階102](../docs/reports/102-known-covariance-gui.md)。科学条件・固定閾値・未知較正の未対応という範囲は段階101と同じである。
