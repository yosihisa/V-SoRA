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


## 用途別の詳細規約

既知モデルの診断APIと、観測データを処理する入口は適用範囲が異なります。式や保存形式の実装があることと、実機の誤差校正・低SNR画像化が完成したことを分けて読んでください。[必要要素と進捗](../docs/reports/overviews/goal-and-progress.md)で接続範囲を整理しています。

### 観測入力・相関・画像化の接続

- [VDIF sessionの受渡し](session-manifest.md)
- [clock mappingと短chunk整列](clock-model.md)
- [周波数分解visibilityと較正](spectral-and-calibration.md)
- [FITS-IDI出力の限定profile](fitsidi-profile.md)
- [VDIFからClosure＋RMLへの短区間profile](closure-pipeline.md)

### 配置・既知天体の条件比較

- [仮想局配置と最大基線長](array-layouts.md)
- [既知天空での配置尺度比較](array-scale-comparison.md)
- [既知天体の局共分散と三次統計の複素rms尺度](bispectrum-known-sky-scale.md)

### 誤差と保存pilotの診断

- [既知の全visibility共分散からClosureへの誤差伝播](joint-closure-noise.md)
- [局の標本共分散からvisibilityの雑音を推定する](sample-visibility-noise.md)
- [相関ファイルから一つの時間・周波数の雑音を診断する](observation-noise-diagnostic.md)
- [既知の線形係数からFFT間の雑音を計算する](filtered-visibility-noise.md)
- [保存pilotの時間散乱診断](pilot-time-scatter.md)

### 三次統計の実験・蓄積・再解析

- [実験用：異なる標本のbispectrum](distinct-sample-bispectrum.md)
- [時間相関と三基線積のモデル検証](temporal-bispectrum.md)
- [三基線積U₃のゼロ源分散と短積分の条件付き感度](bispectrum-sensitivity.md)
- [既知Gaussian電圧モデルの三基線積の全共分散](joint-bispectrum-moments.md)
- [三次統計の追加の和を蓄積する実験API](streaming-bispectrum.md)
- [raw bispectrum NPZ version1](raw-bispectrum-profile.md)
- [保存した三次統計の確認](bispectrum-inspection.md)
- [独立な短積分U₃の等重み平均](bispectrum-window-averaging.md)
- [未知の局gainとbispectrum平均の振幅制約](bispectrum-gain-constraints.md)
- [既知の共通時間相関と三次統計の平均](bispectrum-common-temporal.md)
- [独立周波数群のU₃と電圧標本のまとめ方](bispectrum-independent-group-pooling.md)
- [既知の局・時間共分散による三次統計の母平均](bispectrum-joint-temporal.md)
