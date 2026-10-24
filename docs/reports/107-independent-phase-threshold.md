# 段階107：位相探索scoreの閾値を学習し独立データで評価

- 作成日：2026-10-24
- 状態：完了
- 比較元コミット：c23ff0f6a52e1a92afb0e34ebd163622781fb309

## 読者向け概要

段階104では、局位相を探索した後のscoreを0で分けると、低感度の仮定条件で点源・Cas Aの両方が点源と判定された。このとき正答率0.5だけを見ても、形の情報がないのか、判定の境界が合わないのかを区別できない。

そこで今回は、別の模擬電圧で閾値を学習し、一度決めた閾値を独立した評価データへ適用する。評価データを見ながら閾値を調整しない。結果は条件によって異なり、学習しても必ず良くなるとは確認していない。振幅・SEFD・二つの天空形状は引き続き既知で、実機画像化の方法を完成させた段階ではない。

## 1. 目的・対象範囲

位相探索scoreの固定閾値0と、独立学習した閾値を、同じ評価電圧で比較するnative API/CLIを追加する。既存のGaussian尤度・位相探索・電圧生成部品を変更せず再利用する。GUI・現行U₃・Closure＋RML・Windows収録は変更しない。

1.42 GHz・最大600 m・8局、数百ms〜数秒の短積分を見据えたMの仮定を保つ。未知振幅/SEFD/LOや実OCXOは推定しない。

## 2. 完了条件

1. 閾値選択を独立な全候補の数え上げと照合し、同点・0・固定方向・不正値・未解決を検証する。
2. 学習と評価の乱数系列を分け、3条件・768windowの正式source実験を行う。
3. 未収束を0点や除外にせず、学習不成立・評価不能を明示する。
4. checkout外の導入API・native CLI全JSON、prefix・同梱入力・非上書き、wheel/pip checkを確認する。
5. コードを凍結した両全回帰、学部生向けレポート・索引・公開監査、匿名commit/pushを完了する。

## 3. 実際に行った作業

### 3.1 学習と評価を分ける理由

学習データで誤りが小さくなる閾値を選べても、その値が別のデータで同じ性能を持つとは限らない。そのため、点源/Cas Aの学習用と評価用で電圧の乱数系列を分けた。乱数roleは学習10/11、評価20/21である。局位相も各window内一定・window間独立の仮定で引く。物理的な時間独立性や実FFTを測った実験ではない。

元の位相探索は[段階103](103-gaussian-phase-profile.md)、同じ電圧を使う生成と比較は[段階104](104-paired-phase-template.md)を再利用する。学習器へ渡すのは学習profile scoreの二つの配列だけで、評価score、真の局位相、oracle scoreは渡さない。

### 3.2 一次元の閾値選択

`score > threshold` ならCas A、それ以外は点源という方向を固定する。候補は全unique学習score、0、表現可能な最小score直下。偽Cas A数FP、見逃し数FN、各群の標本数nを用い、`FP*n_casa + FN*n_point` を最小にする。これはbalanced errorに比例する整数で、浮動小数点の同率判定に依存しない。

誤り数は各群をsortし、searchsortedで閾値以下の数を求めて計算する。独立な対象試験では、各候補で一つずつ判定して数える方法と照合した。同率なら絶対値の小さい閾値、次に小さい値を選び、規則を一意にした。評価後にこの規則を変えていない。

入力は有限実scoreの一次元配列で、bool・complex・欠損等を拒否する。最大65536個に制限し、float64へ変換する。学習に未解決があれば閾値を返さず、評価に未解決があれば全体指標を未算出にする。成功例だけを分母にした性能は出さない。

### 3.3 条件と変更ファイル

弱い2条件（M512/19200・SEFD約585966 Jy）と等C零天空1条件を固定した。各生成labelの学習64区間、評価64区間、合計 `3×2×(64+64)=768` 区間。天体flux1000 Jy（零天空は0）、受信機振幅/SEFD、二候補の形状は仮定・既知入力である。Mは独立Gaussian標本数の仮定で、実FFT数や実観測秒数の測定値ではない。

- [追加module](../../apps/simulator/src/vsora_simulator/phase_threshold_validation.py)：閾値学習、固定計画、独立評価、CLI。
- [対象試験](../../apps/simulator/tests/test_phase_threshold_validation.py)：32件。
- [導入照合tool](../../tools/verify_phase_threshold_installed.py)：API・native CLI・全JSON・導入元・非上書き。
- [インターフェース](../../interfaces/phase-threshold-validation.md)、本レポート、索引、正式記録。

## 4. 検証条件・結果

### 4.1 対象試験と正式実験

対象32試験が3.97秒で成功。8seedの独立な候補数え上げ、同点・固定方向・入力非変更、不正配列、固定seed、学習/評価の別role、未収束を模した学習不成立、既存出力の保持を確認した。

正式source実験は20.95秒、子process peak RSS 158304 KiB。全3条件の科学JSONは予備実験と完全一致した。summaryへ入力asset SHAを追加したため、予備との比較は全case JSONを対象とし、導入版との正式比較はsummaryを含む全JSONを対象とした。

| 条件 | M | 学習閾値 | 学習正答率 | 評価oracle | 評価固定0 | 評価学習閾値 | 評価profile AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| t00 | 512 | -0.831874386 | 0.562500 | 0.523438 | 0.500000 | 0.492188 | 0.468262 |
| t01 | 19200 | -5.06289208 | 0.539062 | 0.882812 | 0.500000 | 0.601562 | 0.639648 |
| t02 | 512 | 0 | 0.500000 | 0.500000 | 0.500000 | 0.500000 | 0.500000 |

閾値を学習したt01では固定0より今回の正答率が高くなった。一方、t00では今回の評価で低くなった。学習64標本/labelから得た一回の結果であり、学習変動・他seed・他受信機への改善を保証しない。AUCは閾値変更では変わらず、同じraw profile scoreから計算している。

各評価誤り率の個別95%区間は、今回の固定した学習結果に条件付けた二項区間である。学習を作り直すばらつきは含めず、実画像の信頼区間ではない。AUCの比較対を独立標本として数えず、手法間の差の有意性も検定していない。

### 4.2 導入版と全回帰

両全回帰は各1,931試験成功、除外0件。ソース版586.51秒、導入版587.09秒、両方とも既存警告27,396件。checkout外のAPI2条件とnative CLI全3条件・全768区間の科学JSONが完全一致した。project module23個と参照asset2個のprefix、上書き拒否と全byte保持、wheel内package 98ファイルのsource byte一致、pip check成功を確認した。正式3条件の学習閾値を独立な全候補の数え上げでも再確認し、全384評価予測をscoreと閾値から再計算して一致した。

旧source Python88ファイルは比較元から不変。ソース・試験・検証tool301ファイルを凍結し、全回帰中は変更していない。GUIコードは不変のためブラウザを再実行せず、[段階105の両実Chromium結果](105-paired-phase-gui.md)を参照する。新しい閾値学習CLIはGUIへ未接続である。

再現例：

```bash
python tools/run.py pytest -q apps/simulator/tests/test_phase_threshold_validation.py
python tools/run.py vsora_simulator.phase_threshold_validation --output outputs/phase-threshold --profile full
# 導入済みpackageのnative CLI
python -m vsora_simulator.phase_threshold_validation --output phase-threshold
```

[全学習/評価の記録](../../validation/runs/stage107/reference.json)、[回帰・入力来歴・配布記録](../../validation/runs/stage107/verification.json)、[導入API/CLI照合](../../validation/runs/stage107/installed-api.json)を保存した。大きな電圧配列は保存せず、生成条件・role・seed・同梱入力SHAから再現する。詳細ログとwheelはGit管理外の `outputs/stage107-*` に置く。

## 5. 制約・未解決事項

固定二候補・既知振幅/SEFDの参照であり、閾値を学ぶことは未知受信機を較正することや自由画像を復元することとは異なる。位相探索は3局以上で大域解を保証しない。今回のt01と以前のp05等はseedや評価標本が異なるので、段階をまたいだ数値を対の性能差として扱わない。

独立Gaussian標本・区間内一定位相・window間独立位相は仮定。実FFT独立性、実OCXO、弱実信号の未知LO、実SEFD、実機Cas A画像化、全夜運用、GPU性能、低SNR画像尤度は未検証。新しいGUI操作も本段階では追加していない。

## 6. 次段階

学習閾値・評価score・個別区間・未解決を日本語GUIへ接続する候補。科学的には学習/評価の反復、受信機仮定のずれ、未知振幅/SEFD、局位相の別の扱いを分けて調べる。真値供給・学習による調整・実測・未知画像の復元を引き続き区別する。
