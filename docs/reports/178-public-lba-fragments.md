# 段階178：公開LBA実4局の供給同時刻断片とbit保存

- 作成日：2026-11-03
- 状態：完了（最終正式選択2、準備失敗と初回選択を保持）
- 比較元コミット：`e2feb7688735fa6c0f219c4fcfda9555e6b853e9`（177）

## 読者向け概要

提供者が実天体観測として配布する4局の電圧記録から、同じ**供給時刻**に対応する短い断片だけを取得した。元の2bit情報を読み戻して全byteを再構成し、短いFFTを別計算と照合した。既存の実単局CAMRASや模擬4局を複製したデータではない。

今回の合格は記録の表現と取得境界に限る。実数2偏波のLBADRであり、現製品の複素SigMF形式へそのまま接続していない。供給時計の正確さ、天体検出、実相関・Closure・画像、RTL-SDR/OCXOやCas Aの成功ではない。

## 1. 目的・対象範囲

177後の具体的候補だったDiFX公開記録の観測由来・形式・最小容量を確認し、32MiB以内の少量取得とbit保存検証を選ぶ。同じ模擬codecの条件反復ではなく、実複数局入力の入口を増やす。製品reader/session/clock/API/noise/RMLを変更しない。

変更は [取得・検証workflow](../../workflows/public_lba_fragments.py)、[offline試験](../../tests/integration/test_public_lba_fragments.py)、[取得案内](../guide/public-voltage-data.md)、計画/索引/本report/[text validation](../../validation/runs/stage178/README.md)。元の記録・提供metadata・コード参照・数値配列はすべてGit管理外へ保持した。

## 2. 完了条件

波形の選択取得・数値照合前に、共通の供給UTC `2005-03-11T22:08:40.002Z` から公称0.262144秒を固定。Fs8MHz、4局×2実偏波×2bit、各2097152 time sample、payload各1048576byteを要求した。局ID/偏波順/元offset/headerを保持し、原epoch/Fs/RFを既存profileへ合わせない。

全16777216個の2bit成分をvector unpackと別のu16 scalar法へ厳密一致、全4194304payload byteをrepackして厳密一致させる。固定4窓×4局×2偏波の32rFFT（各256sample/129bin）を独立cos/sin有限和へRTOL1e-11/ATOL1e-8で照合する。窓開始indexは0/262144/524288/1048576、解析scaleは固定code/32768。truthや結果を見て窓/scale/許容を変更しない。MCSEなし、新MC trial0。

## 3. 入力・取得と制約

出典は[DiFX公式datasets案内](https://github.com/difx/difx/wiki/datasets)が指すMPIfR匿名FTPの `lba_4MHz`。既取得README3757byte/inputfiles17106byteのSHAを固定して再利用した。READMEはこの記録をDiFXで試験する操作を案内している。そのtesting/verification用途でローカルな非再配布検証に限定した。別個の明示データライセンス条項は見つからず、コードGPLを観測データの無制限再利用・再配布許諾へ読み替えない。account作成/取得job/人への連絡0。

提供controlは観測V177A、2005-03-11、源1600-445、RF帯域下端1719MHz/USB/帯域4MHz、AT/HO/MP/PAの4局を示す。PAの記録偏波順はL,R、他はR,Lとして保存し、payloadを都合よく入れ替えない。これは提供説明・controlの識別であり、取得波形から天体を新たに検出した証拠ではない。LBAの長基線・周波数・2bit量子化を、目標の600m/1.42GHz/RTL-SDR観測と同一にしない。

元tarは160010240byte、4memberは各40000016byte。その全体を取得せず、tar headerと各16byte旧timestamp header、必要payload範囲だけをFTP RESTで受信した。AT/MP/PAは元時刻22:08:40、HOは22:08:38。元payload内offsetは前者8000byte、HO8008000byte。元headerを別fileとして保持し、切り出し後の時刻へ書き換えた偽の原本を作らない。

成功取得は4196416byte（payload4194304＋file header64＋tar header2048）で約59.42秒。準備probe・失敗時の受信・最終公開probeを含むclient受信総5759344byteで32MiB内。FTPは開始offsetから転送し予定byteで接続を閉じる。ここで数えるのはclientがread/保存したbyteで、TCP/wireやserverが先行送信した全byteは測定していない。

SIZE/MDTM、tar checksum、原headerのSHA、断片の全byte SHAを確認した。未取得archiveや各元memberのfull SHA、producer checksum認証は未検証/null。供給Fsを未知の実sample clockへ代用せず、表示時刻・長さは供給値による公称対応とする。時計補正/geometry/fringe rotationは適用していない。

取得payload断片SHA（各1048576byte、元member全体のSHAではない）：

| 局 | SHA256 |
|---|---|
| AT | `7bcd8fd38cc71f567f197e481c5e38162d98d21e31c98dba3aa30c1a2493deef` |
| HO | `756b60aa3b0aecda1db48c58f6f494a09e3b63cd0491e9d69ffed9cb85564810` |
| MP | `b5f2aa94c75e6149179bf956cc0edec5439dfcae54e31a2d4b969bd6c1f5134c` |
| PA | `46de87cd0389643bb49447046a62c3f030d9c7e4f69d9fe3829512f400051e03` |

## 4. 検証条件・結果

[固定DiFX source](https://github.com/difx/difx/blob/aef8ae38e383565381b939ed4455547f7b990e03/mpifxcorr/src/mode.cpp)の4MHz/2pol/little-endian LBAModeと、[old header分岐](https://github.com/difx/difx/blob/aef8ae38e383565381b939ed4455547f7b990e03/mpifxcorr/src/datastream.cpp)を一次参照にした。既存製品/installed basebandにLBA readerはなかった。DiFX自体を導入・実行した結果ではない。

標準s16 code lookupは8191/-8192/24575/-24576。code規約であって、物理ADC/電圧/gain/SEFD較正ではない。vector bit-plane法と別のu16 word/time/band scalar法で全成分が厳密一致し、元payloadへのrepackも全byte厳密一致した。追加量子化0は元2bit情報の保存を意味し、収録時量子化の損失を回復しない。SigMF/VDIFへ変換していない。

最終正式選択2は両offline unit各12成功/警告0、両study成功。studyはsource依存環境約4.83秒/177 installed依存環境約4.88秒で、10個の保存NPZ fieldと時間/メモリ以外の方法JSONが厳密一致。全65536u16配置のunitは合成bit patternで、独立実観測試行ではない。32FFTの最大絶対差は両環境とも8.816409032730591e-13で固定許容内だった。

公開probeで再生成した取得planは実際の取得planへ厳密一致。全8worker終了、非上書き3件のreturn1だけは意図した拒否で、既存出力/原本SHAを保持した。依存版44件一致。これは同じworkflowのNumPy依存環境比較であり、新しいinstalled製品APIの検証ではない。

製品source/177 wheel/installedの105製品file+4assets全byteと、旧151/168/169/171/172/173/174/175/176/177 prefixを静的照合して保持した。製品変更0、新full/collect/wheel/install/pipcheck/GUI/実相関/Closure/画像fit0。177の両全2524/実GUI等は過去の製品基準の引用で今回へ加算しない。通常GUI151を更新/再起動しない。

凍結1281file/455Python、固定入力283file、131原本76SHA/CAMRAS3SHA/過去原本・参照を保持。追加peakはsource98451456/installed98619392byteで256MiB内、study保存は各10955171byteで64MiB内。初回正式・準備失敗込み追加保存50868916byte/空き41747656704byte（集計時点）で256MiB/10GiB reserve内。

### 全失敗と再実行

初回header probeは4096byte ASCIIの想定でUnicodeDecodeError。受信4608byteを保持し、うち4080byteは旧header後のpayloadだったと記録した。sourceのold-style分岐と現物を確認し、全終了後に16byte限定へ訂正、第二回のindex/header2624byteを別出力へ全再取得した。初回byte列を数値試験の入力へ流用していない。

準備取得attempt1はSO_RCVBUF4096の低throughputで180秒上限に達しTimeoutError、1553072byteと.partial/failure/transfer/log/code/freezeを保持。全終了後だけ受信窓を65536へ変更し、時刻/長さ/解析条件は不変で全4局取得を再実行した。

最初の正式選択は両unit/study/非上書き/byte検査が全成功。その全終了後、取得手順をprivate probeへ依存させないため公開workflowへprobe/plan生成を収容し、live probeを加えた全正式選択を2として再凍結・再実行した。初回成功を合算しない。初回codeは保存済み取得codeのtransport差分から復元し、凍結SHAへ厳密一致するbyte列も保持した。科学条件/入力断片は変えず、新しい数値照合失敗はない。

公開監査指摘0、文書リンク2379件で欠落0。7fileのstrict allowlistで公開し、対象外tracked1603fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・次段階

4局の公開記録断片を取得できたが、共通の公称時刻は物理的なsample同期の測定ではない。配布clock/geometry、偏波、sideband、量子化と実データの時間周波数依存を合わせる次の契約が必要。未取得原本全体の完全性や実FFT独立性、天体検出、検証済み実相関基線、Cas A/RTL-SDR画像の成功を示していない。

次はこの実数2偏波/旧headerの原本を、現製品の複素sample入口とclock/帯域guardへどう対応させるかをreviewする。600m制約や名目Fs/epochを変更して形式だけ通さず、解析的な変換を選ぶ場合も独立受入と全正式予算を先固定する。有限codecと既存Gaussian visibilityを実入力の確率モデルへ合成せず、新尤度や同じ参考画像fit反復へ飛ばない。次文書整理180/予定根本200。
