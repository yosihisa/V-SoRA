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

## 三基線積では、短い積分の雑音も確認する

三基線積の平均の偏りを除いても、その散らばりが小さくなるとは限りません。天体ゼロ・独立な単位power Gaussian電圧という仮定で、異標本量U₃の複素分散は1/[M(M−1)(M−2)]です。Mは独立電圧標本数の仮定で、実機の帯域×積分秒を測定なしで採用できる値ではありません。

三辺の既知相関係数を同じρとすると、三基線積の信号はρ³。標本数を間引くと、偏りを避ける条件を満たせる場合がある一方、三次統計の雑音が増えます。[式と条件付き比較](../../interfaces/bispectrum-sensitivity.md)、[段階057](../reports/057-bispectrum-sensitivity.md)で確認できます。点源の必要反復数は同じbispectrumと正規化を保つ仮定の計算で、実際のCas Aの観測時間・検出確率・画像化の保証ではありません。

## 強い相関と形状の区別は別に確認する

最大基線を小さくすると、Cas Aがほぼ点に見えるため相関fluxは大きくなります。同時に、母集団closureが点源の0から変わる量は小さくなります。信号の強さだけで最適配置を選べない理由です。

[段階081の比較](../reports/081-array-scale-known-sky.md)では、8局・3形状・25〜600mの既知モデルで、相関flux比、母集団closureの点源との差、天体自己雑音を含むU₃のcomplex-rms尺度を並べます。母集団closureは雑音のない相関から計算した値です。全行のRMSには共有baselineと重複があり、独立画像情報量や低SNRの信頼度には変換していません。

```bash
python tools/run.py workflows.array_scale_validation --output outputs/array-scale-comparison
```

1.42GHz・1000Jy、64kHz、0.3/3秒、単一時刻、LO既知補正を仮定します。fringe周期は復元beamの測定ではなく、相関の角度的な周期です。配置の推奨、実観測の画像化成功、必要な観測時間はこの比較だけでは判定できません。
