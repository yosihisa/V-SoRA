# Closure＋RMLによる実観測画像化

更新日：2026-10-02。高精度の受信機・アンテナ較正を用意できないこと、局間LO差があること、一回の積分が数百ms〜数秒というユーザーの条件を採用する。

## 1. どの誤差を消せるか

一時刻・一channelで `V測定_ij = g_i conj(g_j) V天体_ij` と書ける局ごとの未知利得を考える。三局の `arg(V_ij V_jk conj(V_ik))` では局の位相が消える。四局の `log(|V_ij||V_kl| / (|V_ik||V_jl|))` では局の振幅利得が消える。これらをClosure phase、log closure amplitudeと呼ぶ。

**sample時刻や到着時間の整列、積分中の位相回転、局ごとに異なる主ビーム、baseline固有の混入をすべて消せるわけではない。** 局の応答が分離した複素数として掛かるという条件を確かめる。帯域や長時間を先に複素平均すると、この形が崩れる場合がある。Closureは各短積分・各channelから作る。

Closureだけでは絶対fluxと画像の位置原点が決まらない。相対fluxで保存し、位置原点は表示上の約束として記録する。既存Cas A画像を使う場合も、生成形状をそのままRMLの事前画像に与えて成功としない。この情報の自由度と画像化は[Chaelほか、2018](https://arxiv.org/abs/1803.07088)を参照した。

## 2. OCXOの安定性と積分時間

一定の局間周波数差Δrを残してT秒積分すると、相関は中点の位相因子と `sinc(Δr T)` の積になる。中点の位相は局ごとに分離するが、sincによる振幅損失は一般には分離しない。このためClosure amplitudeにも偏りが生じる。sincが負ならClosure phaseにπのずれを生じる組もある。

`|Δr|T ≤ 0.25` は振幅90%以上を残す概算条件。0.3秒なら約0.83Hz、3秒なら約0.083Hzの残留局間差が目安となる。**これは一定差の計算値で、入手予定OCXOの性能測定ではない。** 不規則な位相雑音・温度変化は実測後にモデルを追加する。

短いpilotで周波数差を推定し、IQを補正して再相関する。天体の未知の基線位相を保持したまま時間方向の回転速度を推定する処理を次に実装する。pilotの短さ、推定時間幅、画像化に使う積分時間は別の設定とする。最終積分を数百ms〜数秒に抑え、安定性を見ながら観測時間全体に繰り返す。

## 3. Closureの数と統計

完全なN局網なら独立phaseは `(N−1)(N−2)/2`、N≥4の独立amplitudeは `N(N−3)/2`。4局で3/2、8局で21/20。欠損・低SNR・使わないchannelにより減少する。実装は三角形と四角形を列挙するため、欠損網にある長い閉路をすべて拾うものではない。

現在はbaselineの実部・虚部に同じ独立Gaussian雑音がある近似を使う。各直交成分の逆分散をweightとし、`SNR = |V| sqrt(weight)`、phaseとlog amplitudeの分散を約 `1/SNR²` とする。Closure行列Aに対し `C = A diag(1/SNR²) Aᵀ`。独立な行を選んでも共有baselineによる非対角成分は残るので、C全体を使う。

基線SNR5未満は除外する。この閾値は厳密な低SNR分布の代替ではない。低SNRの非線形バイアス、共通天体雑音、周波数間や時間間の相関は未対応。理論と落とし穴は[Blackburnほか、2020](https://arxiv.org/abs/1910.02062)を参照した。独立集合とGaussian近似が使える条件を数値で評価していく。

## 4. 実装の段階

| 段階 | 内容 | 完了の判定 |
| --- | --- | --- |
| 020 | Closure抽出、独立集合と共分散、有限積分損失 | 任意局利得に不変、Gaussian実験と共分散一致、実IQで損失を確認 |
| 次 | CPUの小規模Closure RML | 勾配の独立数値比較、生成画像と別の事前条件で形状復元、利得誤差不変性 |
| 次 | モデルを必要としないLO差推定 | 未知sky位相を残してrate推定、IQ補正後のClosure回復 |
| 次 | VDIFからRMLまでとGUI入口 | ADC²をJyと偽らず画像化、入力識別・設定・残差・失敗を保存 |
| 後続 | 長時間処理、現実の感度・主ビーム・統計 | 複数乱数seed、未知モデル、実機試験、事前条件依存と不確かさ |

RMLは非負画像、滑らかさ、総相対flux、中心などの条件を置く非線形最適化。局所解があるので複数初期値と事前条件の比較を行う。観測から決まることと正則化で選んだことを結果に分けて記す。

既製候補は[EHT-imaging](https://github.com/achael/eht-imaging)と[SMILI](https://smili.readthedocs.io/en/latest/examples/imaging/imaging.html)。本段階ではインストールも実行もしていない。外部ソフトを導入するときは、その段階で依存関係・ライセンス・入出力互換性を確認する。

## 5. 現在の実行

```bash
python tools/run.py vsora_imaging.closure --input outputs/observation.npz --output outputs/closure.npz
python tools/run.py workflows.closure_validation --output outputs/closure-check
```

入力はlegacy Jy NPZ、spectral Jy/ADC² NPZ、対応FITS-IDI。出力Closure NPZはgeometryと原本SHA-256を保持し、phase=rad、logamp=無次元。未採用値は0とvalid=falseを組で保存する。0だけを測定値として解釈しない。

段階020の数値・適用範囲は[レポート](../reports/020-closure-short-integration.md)を参照。

段階021でCPUのRML参照実装を追加。[入門](../guide/07-closure-rml.md)、[検証](../reports/021-closure-rml-reference.md)。相対fluxの非負画像、弱い中心条件、複数初期値で探索する。Cas Aは停止上限と事前条件の影響が残る。
