# 既知二モデルの独立評価実験

## 目的と実行

点源とCas A形状代理の既知モデルから独立なtraining/holdout電圧を生成し、同じ標本power正規化U₃の実部56＋虚部56を識別する固定の実験である。8局、1.42GHz、最大600m、仮定flux1000Jy。実観測の入力を判定する機能ではない。

~~~bash
python -m vsora_simulator.known_template_validation --profile full --output new-study
~~~

sourceからはworkflows.known_template_validationも使える。fullは固定9条件、各ラベルtraining128・test512。smokeは3条件、training8・test16・M16であり、科学的精度の正式評価には数えない。出力先は新規作成し上書きしない。設定・参照天空は既存同梱assetを用いる。

## scoreと評価の区別

template_score.fit_template_mean_scoreとscore_template_featuresは、trainingの平均差方向と中点を固定してtestを射影する研究用APIである。testで閾値を調整しない。正のscoreをCas Aラベル、0以下を点源ラベルへ割り当てる。分布をGaussianとした尤度や最適分類器ではなく、同じ平均しか得られなければ識別不能とする。

balanced accuracyは二クラスの正答率を等しく平均した量。AUROCはtestのCas A scoreがpoint scoreより大きい割合（同点半分）で、固定閾値の正答率とは異なる。n×n個のscore対を独立試行として数えない。

誤判定率の二項区間は固定trainingの下での独立生成test群ごとに計算する。[SciPyの一次資料](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html)に従い、95% Clopper-Pearson法を使う。trainingの変動、複数条件同時の95%、AUROC、画像信頼度や実機の誤差率を表す区間ではない。誤り0でも区間上限は0ではない。

## 生成条件と制約

独立proper Gaussian電圧に天体自己雑音とreceiver共分散を含める。一定局gainの代数的不変性を少数の同じ実現で確認する。M19200は64kHz×0.3秒に対応づけた理想mode数の仮定で、実FFTの独立性の測定ではない。M512は小さいmode数の比較条件である。

SEFD1000/10000Jyは仮定。約586kJyは直径1m・Tsys100K・効率0.6からの計算例で、実測ではない。trainingとpoint-testのSEFDが違う2条件、および両ラベルが同じ零天空である負対照も含める。

既知の受信機モデル・flux・二つの候補形状を与えた評価であり、未知SEFD、未知天空、時間変動LO、量子化、RFI/品質選別、実機の較正不要を証明しない。scoreは確率や信頼度ではない。低い性能を情報論的な画像化不能の証明にせず、高い性能を実観測の保証にしない。現在のRMLは変更しない。GUIへの追加は後続候補である。
