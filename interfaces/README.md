# ソフト間で揃える情報

相関器と画像ソフトが別々でも、時刻・単位・座標・複素数の符号が一致していれば接続できます。一つでも取り違えると、画像が反転したり、fluxがずれたりします。このフォルダはプログラムが守る規約を定義します。初めて読む場合は[原理](../docs/guide/01-principles.md)と[用語集](../docs/guide/glossary.md)を先に参照してください。

| 文書 | 受け渡すもの |
| --- | --- |
| [session manifest](session-manifest.md) | 各局のVDIFと処理条件をまとめた一覧 |
| [clock model](clock-model.md) | sample0の実時刻と、短区間の実sample rate |
| [相関値と較正](spectral-and-calibration.md) | 時間・周波数・基線別の値、重み、局応答 |
| [FITS-IDIとCASA](fitsidi-profile.md) | 外部ソフトへ渡す相関ファイルと重みの復元方法 |

## 共通の単位・符号

- 設定はJSON、schema_version=1。公開例のsiteは仮想地点です。
- 局位置はsiteを原点とした東・北・上のENU座標、単位m。実測位置を入れるときは座標系・測定誤差を別に残します。
- 天体はICRSの赤経・赤緯、単位度。参照FITSのFK5座標は変換します。
- 時刻はUTC。区間は開始を含み終了を含みません。相関値の代表時刻は積分中央です。
- 基線は局順i<j、ベクトルposition[j]−position[i]。
- 相関値はE[x_i conj(x_j)]。点源の位相はS exp[−2πi{ul+vm+w(n−1)}]。
- u,v,wは波長単位。lは東、mは北、n=sqrt(1−l²−m²)。[式の意味](../docs/guide/01-principles.md)を参照。
- sigmaは複素相関の実部・虚部それぞれの雑音標準偏差。weight=1/sigma²。ゼロ重みは無効です。
- 較正前はADC²、較正後はJy。画像modelはJy/pixel、dirty/restoredはJy/beamです。
- 当面は単一XX偏波です。完全なStokes Iを測ったものとは扱いません。

独自NPZは開発用の形式です。VDIFやFITS-IDIとは役割が違い、他装置のファイルを無条件に読めるという意味ではありません。
