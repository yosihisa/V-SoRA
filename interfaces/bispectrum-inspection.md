# 保存した三次統計の確認

`vsora-bispectrum-inspect --input inputs/raw-bispectrum.npz --source-visibility inputs/shard-00000.npz --output outputs/inspection.json --time-index 0 --channel-index 10`

元相関の指定は必須です。時刻とchannelは0から数える添字で、保存済みのRF昇順を使います。ファイルのSHA、軸、局、単位、保持数と必要な辺平均を照合し、読込中の原本変更と既存出力の上書きを拒否します。

## 状態の意味

- `insufficient_samples`：三局共通FFT数M<3。U₃はJSON nullで、測定したゼロではありません。
- `masked_raw_value`：M≥3ですが、構成基線の品質・RF・仰角等で利用不可。保存値は残し、解析に使える測定とは扱いません。
- `usable_raw_value`：保存形式上の数とflagを満たすraw値です。実FFTの独立性や信頼区間を保証する状態ではありません。

U₃と通常の積は実部・虚部で表示します。通常の積は三局共通集合での三つの辺平均の積です。元相関の二局ごとの有効集合が異なる場合、元相関の三基線積とは異なります。値の差を実機の偏りの推定値とは扱いません。

単位はADC^6またはJy^3の宣言です。相対gain、受信機温度、雑音共分散、位相の不確かさ、検出確率、総fluxや画像は推定しません。現在のRMLの重みと尤度は変更しません。

## 日本語GUIの入力

`POST /api/bispectrum-input` に `input` と `source_visibility` を渡すと、照合済みの時刻・RF軸、局ID順序、単位、二つの入力SHA256を返します。保存NPZだけを受け付け、読込中のファイル状態が変われば拒否します。既存GUIと同じlocalhost・操作ヘッダー・Origin確認を使います。

`POST /api/jobs` の `kind=bispectrum_inspection` は、二つのパス、厳密な整数 `time_index`・`channel_index`、軸読込で得た小文字16進64桁の `raw_bispectrum_sha256`・`source_visibility_sha256` を必要とします。ジョブでも元相関を照合し、選択時のSHAと異なる組なら再読込を求めて停止します。

完了時には同じcell APIの値を `bispectrum-inspection.json` とジョブsummaryへ保存します。GUI表示は実部・虚部を指数表記で丸め、JSONは元の浮動小数点値を保持します。軸やパスの変更、添字の範囲外、原本の不整合は、解析成功として扱いません。
