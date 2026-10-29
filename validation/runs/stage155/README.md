# 段階155：供給受信機の画像依存共分散・勾配・非一意性

[レポート](../../../docs/reports/155-image-covariance-gradient.md)、[条件・一次コードSHA・数値](reference.json)、[正式検証](verification.json)、[全30配列](arrays.npz)。完全log/実行時prefixはGit外 `outputs/stage155-preparation` / `outputs/stage155-*-study`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.image_covariance_gradient_validation --output outputs/new-image-covariance-reference
```

3局/4cell/8x8画像、供給flux/receiver/gainと共通IID proper Gaussianを仮定する計算参照。12決定論的probe/cellはGaussian乱数ではない。100の既存APIを呼び、独立real raw-voltage densityと全64勾配の差分を比較。新尤度API/RML接続/optimizer/画像復元/実機較正なし。二つの異なる正の単位和画像が同じ共分散を作るwitnessも配列へ保持する。151 full/wheel/GUIは引用で今回再実行していない。

nativeはcheckout外cwd、runner/PYTHONPATHなしでworkflowを絶対指定し、全製品moduleは導入prefixから読み込む。main MC0と、既存target内部のGaussian/phase fitting試験を区別する。
