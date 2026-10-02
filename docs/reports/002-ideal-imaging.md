# 段階002：理想visibilityと画像復元

- 作成日：2026-10-02
- 状態：完了（小規模参照実装）
- 比較元コミット：34dd009

## 1. 目的・完了条件

基線、天体方向、時刻からuvwを計算し、解析解に一致するvisibilityと位置・振幅が正しい点源画像を生成する。独立した完全DFT格子で2点源の復元を検証する。

## 2. 実作業

AstropyのEarthLocation/GCRSで幾何を計算。i<j、position[j]-position[i]、E[x_i conj(x_j)]、東・北方向の規約を実装。直接Fourier変換でw項を含むvisibilityとdirty画像を生成。自然重みPSF、小視野Högbom CLEAN、FITS画像、図、JSON結果を出力する。visibilityの独自NPZは標準形式とは区別した。

## 3. 検証結果

`python tools/run.py pytest -q`：**22件成功**。

- uvw基底の軸対応と基線反転、回転後の長さ、積分中央時刻を確認。
- 偏心点源の複素visibilityが独立したスカラー解析解と1e-12 Jy以内で一致。基線反転で複素共役。
- 雑音の実部・虚部それぞれの標準偏差が仮定値と1%以内、seedで再現。
- 完全DFT格子で2点源のdirty画像が入力と1e-12 Jy以内で一致。
- off-center点源の位置、12 Jyの振幅とCLEAN成分総和、PSFの端でwrapしないことを確認。
- CLI相当の結合処理で中心点源1000 Jyを復元。

実行例：

```sh
python tools/run.py vsora_simulator --config configs/experiments/ideal-point.json --output outputs/stage002-point/simulation
python tools/run.py vsora_imaging --input outputs/stage002-point/simulation/visibility.npz --output outputs/stage002-point/imaging
```

4局・600秒、60秒積分、60visibility。CLEAN66反復、成分総和999.044995 Jy、復元ピーク1000 Jy、中心画素一致。結果図と数値は [検証記録](../../validation/runs/stage002/README.md)。

## 4. 制約

- 単一中心周波数、積分中央で評価。帯域平均・積分内変化・一次ビーム・大気・電離層・時計誤差は未導入。
- オフラインIERS表を使用し、今回のEOPはstatus=2（予測値）。警告なしでも実測EOPとは扱わない。
- skyの接平面軸とGCRSの東北軸の微小な差を厳密に追う実観測遅延モデルではない。
- CLEANは小視野でPSFの平行移動を近似。w項が大きい場合に汎用実観測画像化として使わない。
- 復元beamは最大投影基線からの円形λ/B参考値で、PSFの楕円Gaussian fittingではない。
- 残差はdirty-beam単位のまま。復元画像の単純総和を総フラックスと呼ばない。
- Cas Aの広がり、少局での復元性能はまだ評価していない。

## 5. 次段階

Cas Aモデルを座標変換して取り込み、局数・配置・観測時間・仮定感度を比較する。少局・短時間で復元できない条件も結果として保存する。

## 参考

[Astropy EarthLocation](https://docs.astropy.org/en/stable/api/astropy.coordinates.EarthLocation.html)、[NRAO感度の定義](https://science.nrao.edu/facilities/vla/docs/manuals/oss/performance/sensitivity)。
