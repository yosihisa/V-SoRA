# 保存した三次統計の確認

`vsora-bispectrum-inspect --input inputs/raw-bispectrum.npz --source-visibility inputs/shard-00000.npz --output outputs/inspection.json --time-index 0 --channel-index 10`

元相関の指定は必須です。時刻とchannelは0から数える添字で、保存済みのRF昇順を使います。ファイルのSHA、軸、局、単位、保持数と必要な辺平均を照合し、読込中の原本変更と既存出力の上書きを拒否します。

## 状態の意味

- `insufficient_samples`：三局共通FFT数M<3。U₃はJSON nullで、測定したゼロではありません。
- `masked_raw_value`：M≥3ですが、構成基線の品質・RF・仰角等で利用不可。保存値は残し、解析に使える測定とは扱いません。
- `usable_raw_value`：保存形式上の数とflagを満たすraw値です。実FFTの独立性や信頼区間を保証する状態ではありません。

U₃と通常の積は実部・虚部で表示します。通常の積は三局共通集合での三つの辺平均の積です。元相関の二局ごとの有効集合が異なる場合、元相関の三基線積とは異なります。値の差を実機の偏りの推定値とは扱いません。

単位はADC^6またはJy^3の宣言です。相対gain、受信機温度、雑音共分散、位相の不確かさ、検出確率、総fluxや画像は推定しません。現在のRMLの重みと尤度は変更しません。
