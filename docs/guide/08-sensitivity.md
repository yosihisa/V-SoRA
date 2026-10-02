# アンテナの感度と短い積分

## SEFDを計算する

SEFDは、受信機と空などの雑音を、天体のfluxと同じJyで表した値です。小さいほど高感度です。受信機の増幅gainを高くしても、天体と雑音を一緒に増幅するためSEFDは改善しません。

システム雑音温度Tsys（K）、アンテナ有効面積Aeff（m²）から、

```text
SEFD [Jy] = 2761.298 × Tsys / Aeff
Aeff [m²] = 開口効率 × π × 直径² / 4 （円形開口の仮定）
```

SEFD=2kTsys/Aeffは[SKAOの設計書・28ページ脚注8](https://www.skao.int/sites/default/files/documents/d1-SKA-TEL-SKO-0000002_03_SKA1SystemBaselineDesignV2.pdf)に定義されています。係数はSIのBoltzmann定数とJyの換算から計算しました。ここでTsysは天体を外した状態の値です。空・地面・ケーブル損失・受信機雑音を含めます。雑音指数だけから、これらを測定済みと扱うことはできません。円形開口の式が合わないアンテナは、有効面積を直接指定します。

| 直径・開口効率0.6の仮定 | Tsys100KのSEFD |
| --- | --- |
| 1m | 約58.6万Jy |
| 3m | 約6.51万Jy |
| 6m | 約1.63万Jy |

段階024のSEFD1000Jyは、同じ雑音温度・効率で直径約24.2mに相当する計算です。自作アンテナの性能を実測した値ではありません。必要直径の断定でもなく、成功条件がどれだけ高感度だったかを見る換算です。

## 一回の積分で得るSNR

一基線・一偏波・弱い天体では、雑音の目安は[式](https://science.nrao.edu/facilities/vlba/docs/manuals/oss2013a/baseline-sensitivity)で計算できます。

```text
雑音σ [Jy] = sqrt(SEFD_i × SEFD_j) / (処理効率 × sqrt(2 × 有効帯域Hz × 積分秒))
SNR = その基線の相関flux / σ
```

長い基線ではCas Aが拡がって見えるため、相関fluxは総flux1000Jyより小さくなります。Closure phaseには三角形の3本、amplitudeには四角形の4本が必要です。強い一本があっても、残りの辺が弱いと現在のSNR10処理では使えません。

計画ソフトでは、Cas Aの総powerを各SEFDへ加えて雑音を見積もっています。これは正規Gaussian電圧の実部・虚部の分散を平均した近似です。自己雑音の基線間共分散・主ビーム・RFIは含めていません。表示するClosure数は**雑音を引く前の期待値**で、検出確率やLO探索の成功率ではありません。

## 帯域と短い積分の制約

現在のVDIF試験は256kHz幅のchannelごとにClosureを作ります。2.048MHzを一つのcoherent channelとして使えれば雑音は減りますが、RFごとの幾何と局bandpassを扱って情報を集める必要があります。別channelの複素平均を無条件に行える、という意味ではありません。

LO差を補正した後も残差rateがあると、積分中に信号が回転します。一定rateの90%coherenceの条件は約 |残差Hz|×積分秒 ≤0.2504です。0.3秒では約0.835Hz、3秒では約0.0835Hz以下が目安です。非線形な位相揺れは、この一定rateの式だけでは評価できません。

短い露光を増やすと基線の方向と情報数は増えますが、一露光のSNRは上がりません。弱い信号を長時間集めるには、低SNRの統計を適切に扱う方法、rateを追うための基線、アンテナの面積と受信機雑音を併せて検討します。

## GUIと計算

GUIの「感度計画」で面積・Tsys・0.1/0.3/1/3秒・帯域・配置を変えます。4時間に16短露光を分散する計算です。画像は復元せず、期待phase/amplitude数と許容残差rateを表示します。入力とsummaryは履歴に保存できます。

```bash
python tools/run.py workflows.sensitivity_validation --output outputs/sensitivity-grid
python tools/run.py vsora_simulator.sensitivity --config configs/experiments/ideal-point.json --integration-s 0.3 --bandwidth-hz 256000 --output outputs/sensitivity-plan
```

[段階025の比較](../reports/025-sensitivity-planning.md)には、SEFD1000〜100万Jy・0.1〜3秒の条件と制約を残しています。
