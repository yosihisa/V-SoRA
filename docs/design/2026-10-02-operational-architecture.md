# 収録と解析の分担、容量、PC構成の概算

- 作成日：2026-10-02
- 種別：資料と計算に基づく初期設計。実機の速度測定・購入機種の選定ではない。

処理の意味は[入門ガイド](../guide/README.md)を先に参照してください。ここでは「どのPCで何をするか」「どれだけ保存領域を使うか」を見積もります。現在の実装は[開発計画](development-roadmap.md)、正確な受け渡しは[interfaces](../../interfaces/README.md)が基準です。

## 1. 概算の前提

| 条件 | 仮定 |
| --- | --- |
| 対象 | OCXO改造RTL-SDR、Cas A、1.42GHz、最大基線約600m |
| 局数 | 4局を基準に8局へ拡張。各局1受信機・1Windowsノート |
| 観測時間 | 4時間 |
| sample rate | 2.048MHz。これはRF周波数とは別の量 |
| 記録値 | 一つの複素sampleに8bit I+8bit Q、合計2byte |
| 相関出力の概算 | 1024channel、単一偏波、補正後に1秒積分 |
| 単位 | MB/GB/TBは10進、MiB/GiBは2進 |

局数・時間・実測感度はまだ確定していません。以下はこの表の条件を置いた計算です。

## 2. ソフトとPCの分担

| 工程 | 実行場所 | 入出力と担当 |
| --- | --- | --- |
| 収録 | 各局Windows | 受信機設定、IQ記録、実sample時刻の根拠、欠落情報。ハードウェアに合わせて後で開発 |
| 入力整理 | GPU搭載Linux/WSL Ubuntu | 原本checksum、時刻・周波数・局位置をまとめ、必要ならVDIFへ変換 |
| 相関 | Linux/WSL | 時計・幾何・位相を合わせ、時間/周波数/二局ごとの複素相関値を作る |
| 較正と画像化 | Linux/WSL | 基準天体等から受信機応答を求め、Jyへ較正し、画像へ復元 |
| シミュレーション | Linux/WSL | 正解の天体から模擬IQ/相関値を作り、同じ処理へ渡して比較 |
| 操作と実行記録 | Linuxの処理＋Windowsブラウザ | 日本語GUI、条件保存、進行状態、画像と数値の比較。次段階で実装 |

収録器から**直接VDIFへ保存してもよい**設計です。IQ/SigMFの原本からLinuxで変換する方法も選べます。どちらでも、VDIF以外の時刻測定・局位置・周波数・欠落情報を付けます。直接VDIFにしただけでsample時刻が正しく測れるわけではありません。

相関器・画像ソフトは自作と既製品を差し替えられるよう、ファイル規約を揃えます。現在は自作CPU参照実装とCASAの限定接続を確認しました。DiFX/SFXC/WSCleanなどの候補全体を実行確認したわけではありません。

## 3. 観測データのまとめ方

```text
session/
  observation.json        # 天体・RF・局位置など共通条件
  manifest.json           # 局別ファイル・sample数・checksum・完了状態
  stations/ST01/
    receiver.json         # 設定・基準発振器・量子化・偏波
    timing.json           # sample番号とUTCの対応、測定法と誤差
    events.jsonl          # 欠落・設定変更・連続性の記録
    chunks/               # IQ/SigMFまたはVDIF
```

これは将来の観測パッケージ案です。現在の相関CLIへ渡すmanifestは[実装済み仕様](../../interfaces/session-manifest.md)を使います。この設計案と実装済み項目を混同しません。

重要な情報は、実sampleの時刻、実sample rate、RF設定、I/Qの向き、局位置・座標系、偏波、量子化、無効区間、ソフト版です。時刻はUTCとsample番号の対応で保持し、測定・推定・仮定を分けます。標準RTL-SDR APIにはsample対応のハードウェア時刻引数がないため、GNSS/PPSとsampleを結ぶ方法は追加設計が必要です。[librtlsdr API](https://github.com/osmocom/rtl-sdr/blob/master/include/rtl-sdr.h)

原本を保持し、収録未完了は`.partial`や状態情報で区別します。搬送後にchecksumで同じファイルか確認します。実測局位置やserialを公開Gitへ入れず、公開例は仮想地点と局IDを使います。

## 4. IQとVDIFの容量

一秒のIQはFs×2byteです。2.048MHzなら約4.096MB/s、4時間なら約58.98GB/局になります。

| データ | 1局 | 4局 | 8局 |
| --- | ---: | ---: | ---: |
| 4時間IQ | 約58.98GB | 約235.93GB | 約471.86GB |
| 4時間VDIF | 約59.21GB | 約236.85GB | 約473.70GB |
| IQ原本とVDIFを両方保持 | 約118.19GB | 約472.78GB | 約945.56GB |

VDIFは32byte header＋8192byte payload、4096sample/frame、500frame/sを仮定しています。現在のEDV0/8bit complex検証もこのframe条件です。2.4MHzならIQは4.8MB/s、4時間で約69.12GB/局へ増えますが、そのFSのVDIF条件は別確認が必要です。

60秒IQは約245.76MB/局です。ファイルを短く分割すれば扱いやすくなりますが、分割の境界でsampleが失われないよう、番号と連続性を保持する必要があります。

## 5. 相関出力と画像の容量

相互基線数はN(N−1)/2。将来の自己相関も含めると積数はN(N＋1)/2です。複素値8byte・重み4byte・flag1byteで見積もる単純モデルは次の式です。

```text
容量 ≈ 積数 × channel数 × 観測秒数/積分秒数 × 13byte
```

| 局数 | 相互基線 | 自己込み積数 | 1024channel/1秒/4時間の要素概算 | 作業領域の目安 |
| --- | ---: | ---: | ---: | ---: |
| 2 | 1 | 3 | 約0.58GB | 3～10GB |
| 4 | 6 | 10 | 約1.92GB | 10～30GB |
| 8 | 28 | 36 | 約6.90GB | 30～100GB |

FITS/MSには複数の列、索引、較正済みコピーがあり、実サイズはこの要素概算より増えます。現在の自作FXは相互基線を出力し、上表の自己相関込み保存をすべて実装したわけではありません。

0.1秒積分なら容量10倍、0.01秒なら100倍です。8局・4時間・0.01秒保存では要素だけで約690GB。時計・LOを補正する前に長く平均すると信号が消えるため、まず短い較正区間を処理し、その後に平均時間を決めます。

512×512のfloat32画像は1枚約1.05MBです。1024channelの画像cubeは約1.07GB/列。通常の連続波画像数枚はIQに比べて小さいですが、処理途中の配列は増えます。

## 6. 保存・搬送

| 用途 | 4局・4時間 | 8局・4時間 |
| --- | --- | --- |
| 各収録PC | SSD空き100GB以上/局 | 同じ |
| Linux作業SSD | 1TB程度から評価 | 2TB程度から評価 |
| 1観測のIQバックアップ | 約236GB | 約472GB |
| 10観測のIQ原本だけ | 約2.36TB | 約4.72TB |

容量へ25%以上の余裕を加え、バックアップは別媒体と数えます。短積分の全時間保存や複数観測の同時処理は再見積もりします。大容量データはGit管理外です。

| 仮定した集約速度 | 4局IQ約236GB | 8局IQ約472GB |
| --- | ---: | ---: |
| 10MB/s | 約6.6時間 | 約13.1時間 |
| 100MB/s | 約39分 | 約79分 |
| 250MB/s | 約16分 | 約31分 |

通信・SSDを測った値ではありません。checksumや追加コピー時間は含みません。収録は各局SSDで完結させ、観測後にEthernetまたは外付けSSDへ集約する方式を初期候補とします。

## 7. CPU・RAM・GPUの目安

1024点複素FFTと基線の積和だけを単純化すると、4局約0.51GFLOP/s、8局約1.28GFLOP/sの算術量です。補間、遅延探索、RFI、I/O、MPI等を含まず、Python処理の実速度を保証しません。

8局×1秒のcomplex64電圧bufferは約125MiBです。小さい区間で処理すれば、4時間分を全てRAMへ読む必要はありません。

| PC | 初期に評価する構成 | 判断に必要な測定 |
| --- | --- | --- |
| 各Windows収録 | 4CPU core程度、RAM8～16GB、SSD | 約4.1MB/sを欠落なく長時間記録できるか |
| 4局Linux処理 | 8CPU core程度、RAM32GB、SSD1TB | 代表データの処理時間・最大RAM・I/O |
| 8局Linux処理 | 12～16core程度、RAM32～64GB、SSD2TB | 時計探索を含む全処理の実時間比 |
| GPU | CPU基準経路では必須ではない | 重い処理と対応ライブラリを選んでから評価 |

これらは購入推奨や実測最低要件ではありません。GPUを搭載しても、現在のNumPy/CPU実装は自動的にGPUへ移りません。CUDA/xGPU等を組み込む場合は、その処理を明示的に開発します。

将来、同じ10分の8局データ（IQ約19.7GB）で、処理時間・最大RAM/VRAM・読出し速度を比較します。実時間の2倍の速度なら4時間分の相関を約2時間で終える計算ですが、搬送・時計探索・較正・画像化は別に加算します。現時点でこの速度試験は未実施です。

## 8. まだ決める必要があること

局数、観測時間、アンテナ感度、時計とsampleの対応方法、実測位置、RFI環境、較正天体、保存期間、使うLinux機の仕様です。最初の判断材料は実sample時刻・周波数・位相がどれだけ安定するかです。

## 参考資料

- [Baseband VDIF](https://baseband.readthedocs.io/en/stable/vdif/index.html)：frameとsampleの入出力
- [SigMF仕様](https://sigmf.org/)：IQと補足情報の保存
- [CASA importfitsidi](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.data.importfitsidi.html)：FITS-IDIからMS
- [WSClean](https://wsclean.readthedocs.io/en/latest/usage.html)：MSを使う画像復元候補
- [DiFX](https://github.com/difx/difx)、[xGPU](https://github.com/GPU-correlators/xGPU)：相関器・GPU積和の候補
