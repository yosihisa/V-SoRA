# 段階005：模擬IQからFITS-IDI候補を経た画像復元

- 作成日：2026-10-02
- 状態：完了（限定profile・静的snapshot）
- 比較元コミット：c3d4524

## この段階の読み方

模擬IQからファイルの受け渡しを経て画像まで、処理全体をつなぎました。この時点のFITSの複素共役には後に外部ソフトとの違いが見つかり、段階006で修正しています。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・完了条件

各局の模擬電圧→VDIF→遅延補正・FX→交換ファイル→画像復元を実際に接続する。実露光と時刻間隔を区別し、形式の符号・重みを検証する。

## 2. 実作業

Memo 114の限定FITS-IDI候補を追加。内部のsecond−firstと標準のfirst−secondの基線座標を変換。時刻、局座標、単一XX、NORMAL重み、1channelを保存。独自の観測設定は追加テーブルに置く。[profile](../../interfaces/fitsidi-profile.md)。

8局の非規則2D・600 m・仮想地点・4時間の中に16snapshotを配置。各snapshotは4096×64=262144 sample、2.048 MS/sで0.128秒。各局にSEFD1万Jyの独立雑音を加え、Cas A1000 JyのGaussian自己雑音も含めた。VDIFは8bit、既知幾何遅延のみを補正。snapshot内は静的でFFT周期のモデル。

## 3. 検証結果

自動検証 **33件成功**。FITS checksum、時刻、基線番号・uvw符号、局座標、重み、XX、点源のIDI→画像結合を確認。

初回結合実行で、FITSから読み戻したfloat32重みの総和がPSF中心の丸め誤差を起こし、CLEANの正規化検査に失敗。dirty画像の重み・visibilityの積和をfloat64/complex128へ明示変換し、再現テストを追加。修正後に再実行して成功した。

| 指標 | 結果 |
| --- | ---: |
| span | 4時間 |
| **実露光合計** | **2.048秒** |
| 各snapshotのvisibility相対誤差平均 | 約10.0% |
| IDIのfloat32読み戻し相対差 | 1.90e-8 |
| 共通110秒角モデルのNRMSE | 0.0567 |
| 相関係数 | 0.99969 |
| 成分フラックス比 | 0.936 |

16回×0.128秒の短時間収録を900秒間隔で置いた。4時間連続収録と同じ感度ではない。INTTIMと重みには0.128秒を使用。FFT binの平均周波数は設定RFから−16 kHzなので、continuumの周波数とuvwをその平均へ対応させた。

## 4. 再現・保存先

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.iq_to_image --output outputs/stage005-iq-image-v2
```

結果・交換ファイル・画像図は [検証記録](../../validation/runs/stage005/README.md)。大容量の局別VDIFはGit管理外。出力先は新しい名前を使う。

## 5. 制約と次段階

時計・LO差は既知幾何以外にない。スケールは模擬sqrt(Jy)に既知。連続時刻の遅延補間、整数sample位置合わせ、未知時計探索、実データ振幅校正は未完成。

内部IDIの構造検証と自分のreaderだけでは外部互換性を証明しない。CASA互換性を別環境で確認する準備を進めているが、本段階の成功条件には含めない。次段階で外部読込み・独立画像化、続いて未知誤差への対応を進める。
