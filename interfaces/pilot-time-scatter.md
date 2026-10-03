# 保存pilotの時間散乱診断

`vsora-time-scatter`は、選択したRF channelの時間cellを並べ、時間方向のpowerを計算する受動診断です。入力は閉じたnative spectral NPZと、任意の保存rate profileです。

```bash
vsora-time-scatter --input pilot/shard-00000.npz --channel-index 16 \
  --rate-profile rate-linear.json --output time-scatter.json
```

## 条件と入力

- 32〜8192個の非重複時間cell、正の保存`integration_s`。時間×基線形式では各時刻の基線露光が等しいこと。
- 段階047の局power・quality flag・局と基線の共通FFT数、全基線、局ID、同一単位。
- 全cellが一cell雑音診断の条件を満たすこと。不適格なcellを黙って除外せず、系列を「未判定」にする。
- 追加profileを渡すときは、保存相関の補正が明示的に未適用であること。局ID・UTC原点・時刻範囲を検証し、二重補正と外挿を拒否する。

profileなしでは保存値をそのまま使います。profileありでは、cell中心時刻で局位相差を引きます。Vij = E[xi conj(xj)]なので、正の局rate差が作る位相へ負の回転を掛けます。cell内の積分損失を回復する操作ではありません。

## 雑音を引いたpower

T個の相関値を zₜ、真の平均を μₜ、平均0の雑音を εₜ とします。FFT数Mが全局・基線で共通の独立proper Gaussian電圧の場合、同じ標本の局power P̂i,P̂j と相関 V̂ij から、複素雑音分散の条件付き不偏推定は次式です。

ν̂ₜ = (M P̂i P̂j − |V̂ij|²) / (M² − 1)

実装は段階046/047の全実共分散の対応する実部・虚部対角を足し、この式と一致する値を使用します。

- 時間power：Ptime = 平均(|zₜ|² − ν̂ₜ)
- 平均power：Pmean = |平均(zₜ)|² − Σν̂ₜ / T²
- excess scatter：Ptime − Pmean

独立な時間雑音と、データから独立に固定した回転の条件では、期待値はそれぞれ平均|μₜ|²、|平均μₜ|²、その差です。profileを同じpilotから推定すると依存が生じ、この単純な不偏性を保証しません。有限FFT雑音モデルもFIR・量子化・変動時には近似です。

比Pmean/Ptimeは、Ptime>0なら計算します。負や1を超える値を切り詰めません。不偏なpowerの比が不偏になる保証はありません。Ptime<=0または数値範囲外なら比はnullで、その基線を未判定にします。全体の`conditional_estimate`は基線がすべて有効という意味ではありません。

powerの単位はADC^4またはJy^2です。比はpowerの比であり、振幅の保持率ではありません。振幅変動・天体のUV変化・RFI・雑音モデルの差もexcess scatterを作ります。一定の局gainなら全powerに同じ|gi conj(gj)|²が掛かり、比は不変です。

## 出力と制約

JSONに時刻・RF・局ID・公称FFT数範囲・基線別raw/差引power・平均相関・無制限の比、入力とprofileのSHA256を保存します。上書きと読取中に変わった入力を拒否します。出力に個人のローカルパスを埋め込みません。

FFT/time cellの独立性、実機のcoherence、信頼区間、profile推定依存性は未校正と明示します。雑音の大きさや閾値を画像の採否へ適用せず、RMLの重みも変更しません。aliasやcellより速い変動・すでに失われた信号は検出できない場合があります。

[一cell雑音の規約](observation-noise-diagnostic.md)、[固定係数の時間相関モデル](filtered-visibility-noise.md)、[段階051レポート](../docs/reports/051-pilot-time-scatter.md)を参照してください。
