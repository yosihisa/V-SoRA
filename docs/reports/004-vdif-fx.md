# 段階004：短時間模擬IQ・VDIF・FX相関

- 作成日：2026-10-02
- 状態：完了（静的snapshot参照系）
- 比較元コミット：34f21fe

## この段階の読み方

画像から相関値を直接作る試験に続き、各局の電圧であるIQを作りました。VDIFへの保存と読込み、FFT後の相互乗算が既知の値へ近づくかを試しました。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・完了条件

複素IQを実際のVDIFへ保存して読み戻し、相関器で解析値と一致するvisibilityを得る。時計差や連続的な追跡に進む前に、符号・量子化・無効フレーム・FFT正規化を確認する。

## 2. 実作業

- Baseband 4.3.0をローカル環境へ導入し、EDV0・1thread・1channel・8bit複素のVDIF adapterを作成。
- 4096 sample/frame、2.048 MS/sでは500 frame/s。全フレーム単位の無効区間を保持。欠落・重複・時刻順序・局ID違い・切れた末尾を拒否。
- Baseband/mark5accessのoffset binary規約（byte−127.5）/35.5を確認。模擬sqrt(Jy)電圧のスケールをJSONへ保存。
- 単位的FFT、矩形窓、非重複ブロックのFXを実装。局ごとの既知遅延をRF＋ベースバンド周波数で補正。無効サンプルは基線ごとに除外。
- PSDの空の共分散からGaussian電圧を生成。相関器の補正コードを生成器から呼ばず、逆向きの位相を独立に記述。

## 3. 検証結果

`python tools/run.py pytest -q`：**30件成功**。

- 共通信号と複素局ゲインの相関が独立した時間領域の平均電力と1e-12以内で一致。
- 既知の小数sample遅延を補正してGaussian相関値が4%以内、未補正では大きな誤差。
- VDIF量子化誤差が1量子化幅以内。無効frameの時刻を詰めない。
- 欠落・末尾切断・局ID違いの拒否を確認。
- VDIF→FXの連続結合処理で独立した時間相関との誤差0.1%未満。

実行例：

```sh
OPENBLAS_NUM_THREADS=1 python tools/run.py workflows.iq_roundtrip --output outputs/stage004-iq
```

4局、2点源1000 Jy、262144 sample/局、0.128秒、64点FFT・4096ブロック。

| 指標 | 結果 |
| --- | ---: |
| 浮動小数IQと期待visibilityの相対誤差 | 2.330% |
| VDIF経由と期待visibilityの相対誤差 | 2.329% |
| VDIF量子化による追加差 | 0.0441% |
| 遅延未補正の相対誤差 | 138.5% |
| 各局クリッピング | 0% |

参照との差の主成分は有限Gaussian標本の自己雑音。期待値への一致を全チャネルでゼロ誤差とは要求しない。[詳細](../../validation/runs/stage004/README.md)。

## 4. 制約

IQは静的幾何のFFT周期snapshot。連続観測で変化する幾何遅延、整数sample位置合わせ、時刻誤差、LO driftの処理はまだない。既知の遅延を周波数領域で完全に与えており、未知時計を天体から解いたものではない。

VDIF読込みは短いファイルを全体読込みする参照実装。startは整数UTC秒、EDV0以外を拒否。実受信機の量子化や振幅校正は別であり、模擬scaleを実データに自動適用しない。DiFX等の外部読込みは未検証。

Baseband内部でNumPy 2.5のshape代入に関するDeprecationWarning（今回37件）がある。結果の失敗ではなく依存ライブラリの将来互換性の課題として記録する。時刻文字列の桁数差による初回テスト失敗は、Timeの数値比較へ修正した。

## 5. 次段階

VDIF相関結果を時刻・uvw・周波数付きで交換形式へ渡し、模擬IQから画像まで接続する。その後、連続時刻と未知時計・LOの補正を段階的に追加する。

## 参照

[Baseband VDIF](https://baseband.readthedocs.io/en/stable/vdif/index.html)、導入版のbaseband.vdif.payload.encode_8bit/decode_8bitを確認。
