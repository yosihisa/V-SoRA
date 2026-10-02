# 段階015：短いpilot積分と入力検査

- 作成日：2026-10-02
- 状態：完了（EDV0の4096sample frameを等分する積分）
- 比較元コミット：77346b6

## 1. 目的・対象範囲

短い積分でfringe rate探索のalias間隔を広げる。設定の誤字やFITS数値溢れを処理前に拒否し、不正な条件を黙って使用しない。

## 2. 完了条件

VDIFの2ms frameから1ms積分を生成し、積分数・時刻・露光時間・buffer上限が一致する。未知の設定キー、非mapping入力、FITS float32溢れを拒否。全回帰成功。

## 3. 実際に行った作業

- `session.py`：積分長がframe長を等分する場合を許可。frameを読むたびに共同bufferから必要sampleを順に切り出す。
- `config.py`：site/source/observation/image/noiseと局記述のキー、mapping、局数、ENU長、diameterを検査。schema versionにbooleanを受理しない。
- `fitsidi.py`：FLUXをfloat32へ変換する前に範囲を検査。
- `aligned.py`：幾何補正を使うCLIでphase_center_correction=falseを拒否。
- 対応する単体・統合試験を追加。

## 4. 検証条件・結果

```sh
.verification-venv/bin/python tools/run.py pytest -q
```

- 独立Python環境で **68件成功**。BasebandとNumPyの既知DeprecationWarning **745件**。
- FS2.048MHz、frame4096sample、積分2048sample。131072sampleから **64積分×1ms** を生成し、4096sample/局bufferを確認。
- timestamp差・有効露光は1ms。短い積分はSNRを下げるため、fringe探索区間全体での積算が必要。
- 現在のFFT法ではdelay alias周期1/Δf、rate alias周期1/Δt。1ms間隔ならrateの周期1000Hz（探索はその半周期より狭く設定）。これは計算上の範囲で、実機の検出保証ではない。
- 5種の未知nested keyと3種の非mapping rootを拒否。1e40のvisibilityはファイルを書かず拒否。

詳細：[summary](../../validation/runs/stage015/summary.json)。実機VDIFでは未検証。

## 5. 制約・未解決事項

積分長はframeの整数倍または約数。任意長積分、RFI channel選択、実時計の長時間追従は別段階。frame内部の欠落sampleはVDIF EDV0のinvalid bitだけでは表現できない。

## 6. 次段階

既製画像復元ソフトへ、入力の重みとflagを保って渡す実用アダプターを作る。
