# ソフト間の規約（version 1）

- 設定はJSON。schema_version=1。siteは公開の仮想地点で、観測局の実測位置ではない。
- 局配置はsiteを原点とするEast/North/Upのm単位。IDは一意。偏波は当面単一の理想同偏波。
- sourceはICRSの度単位。参照画像のFK5座標は取り込み時にICRSへ変換する。
- 時刻はUTC、収録区間は開始を含み終了を含まない。visibility時刻は積分中央。
- 基線はID順のi<j、ベクトルはposition[j]-position[i]。
- visibilityは E[x_i * conj(x_j)]。位相追跡後の点源は S exp(-2πi(ul+vm+w(n-1)))。
- u,v,wは波長単位。lは東、mは北、n=sqrt(1-l²-m²)。画素値はJy/pixel。
- 雑音sigmaはvisibilityの実部・虚部それぞれの標準偏差。weight=1/sigma²。
- 独自NPZは開発用の中間形式。FITS-IDI/VDIFの互換性を保証する形式とは呼ばない。
- 将来の実収録入力はVDIFと時刻・周波数・局位置・偏波・欠落情報。実機同期仕様は未確定。
