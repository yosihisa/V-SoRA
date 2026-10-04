# raw bispectrum NPZ version1

## 目的

三次統計の追加の和を、元のvisibilityと対応する独立したファイルへ保存します。異標本三基線積U₃を後から再計算できます。実FFTの独立性や画像の信頼度を保証する形式ではありません。

## 配列

Tは時刻数、Fは全FFT channel数、Kは三角形数です。

| 名前 | shape | 内容 |
|---|---|---|
| triangles | [K,3] | 局配列の添字、重複しないi<j<k |
| times_s | [T] | UTC原点からの積分中心秒、実数・非負・昇順 |
| frequencies_hz | [F] | RF周波数、実数・正・昇順 |
| common_fft_count | [T,K] | 三角形の3局共通の保持block数、0〜100万 |
| nominal_fft_count | [T] | 全block数、共通数以上 |
| edge_sums | [T,F,K,3] | A=Σa,Σb,Σc、辺a=ij,b=jk,c=ki |
| paired_edge_sums | [T,F,K,3] | H=Σab,Σac,Σbc、この順序 |
| triple_edge_sum | [T,F,K] | J=Σabc、丸め範囲で非負実数 |
| channel_triangle_usable | [T,F,K] | 利用可否、共通数3未満はfalse |

raw sumsは有限な複素配列で、保持数0の和は0です。3〜8局・FFT長2〜4096・T×F×K最大262144に限定します。M<3のU₃は0を返し、利用不可の標識を併記します。0を測定したという意味ではありません。U₃は和と保持数から再計算し、重複保存しません。

## metadata

局ID順序、UTC原点、電圧単位（ADC／sqrt(Jy)）、FFT長、標本周波数、元visibilityのSHA256、処理の説明を必要とします。局IDは3〜8個の重複しない英字始まりの英数字・underscore・hyphen、最大32文字です。三基線積の単位はADC^6／Jy^3。単位の宣言と較正の実施は別に確認します。

辺の順序、独立性・maskの独立性・Gaussian尤度・角度の不偏性・実機検証・現行RMLへの適用を未確認とするflagを保存します。未確認flagをtrueに上書きすることは、このversionでは受け付けません。

## APIと元ファイルの照合

- `vsora_formats.bispectrum.save_bispectrum(path,data,metadata)`：厳密な入力検査後、新規NPZへ保存。既存出力を上書きせず、保存失敗時は一時ファイルを清掃します。
- `load_bispectrum(path,source_visibility=None)`：pickleを使わず読み、U₃と利用可否を返します。照合を省略した場合は`source_visibility_verified=False`です。
- 元のspectral NPZを指定すると、SHA256、時刻・周波数・局ID順・UTC原点・単位・FFT長・標本周波数を照合します。共通数が各辺の保持数を超えていないか、利用可の三角形に無効な辺がないかも確認します。
- 三局共通集合が各辺の集合の部分集合であるという定義に従い、保持数が同じ辺は同じ有効集合として、A/Mと元のvisibilityを照合します。向きkiの辺には共役を使います。

識別情報の確認は、生電圧からの処理履歴が全て正しいことの証明ではありません。異なる有効集合の追加の和は、平均visibilityだけから照合できません。

NPZの余分な項目、object配列、不正version/header、宣言容量とpayloadの矛盾、非有限値、不正なshape・単位・標本数を拒否します。宣言非圧縮容量は40MiBまでです。未知の雑音共分散の推定、局power正規化、RMLへの適用は含みません。

[蓄積式](streaming-bispectrum.md)、[段階062レポート](../docs/reports/062-bispectrum-sidecar-format.md)
