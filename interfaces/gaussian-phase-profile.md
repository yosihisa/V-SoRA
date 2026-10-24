# 既知振幅・雑音で局位相だけを合わせる参照API

## 入力と前提

`vsora_correlator.gaussian_phase_profile` は、既知共分散Gaussian APIの拡張部品。入力は全局で共通の独立な複素電圧標本から計算した `S = X.T @ X.conj() / M`、候補共分散 `C`、独立標本数 `M`。平均0でproperな複素Gaussian、区間内一定の局位相、既知の振幅・SEFD・天空候補を仮定する。三角形ごとに異なる標本から全局Sを作らない。

`C` は正定値Hermitian、`S` は半正定値Hermitian、局数1〜16、`M` はboolを除く整数1〜2^53。数値検査は[既知共分散API](known-covariance-gaussian.md)を継承し、非零係数が丸めで消える場合等を拒否する。

## 呼び出し

```python
from vsora_correlator.gaussian_phase_profile import (
    fit_station_phases, compare_phase_profiles, PhaseProfileConvergenceError,
)
fit = fit_station_phases(C, S, M, max_iterations=200)
comparison = compare_phase_profiles(C0, C1, S, M, max_iterations=200)
```

`C(phi)=D C D^H`, `D=diag(exp(i*phi))` とし、基準局の位相を0へ固定する。各候補についてGaussian負対数尤度を局位相で小さくする。`max_iterations` はboolを除く整数1〜1000。

## 結果

- `candidate_phase_rad`：基準局に対する候補位相。真の受信機位相を同定したという意味ではない。
- `fitted_covariance_real_imag`：最終次元が `[real, imag]` の候補共分散。
- `nll_without_constant`：共通の `M*n*log(pi)` を除いた負対数尤度。
- `phase_dependent_trace_per_mode`：対角定数を除いたtrace/Mの位相依存部分。最適化内部はさらに係数を規格化する。
- `gradient_inf_norm_normalized`：内部規格化後の勾配最大絶対値。物理的な位相誤差・信頼区間ではない。
- `optimizer_runs`：各開始点の成功フラグ・反復数・勾配・終了メッセージ。3局以上で2n開始点。
- `state`：`phase_independent`（位相に依存しない）、`analytic_two_station`（2局解析解）、`stationary_candidate`（局所停留候補）、`not_converged`（確認できず）。

3局以上はL-BFGS-Bの成功と規格化勾配≤1e-6を確認し、最小の観測目的値と丸め許容内で一致する成功候補を採用する。大域解は保証しない。位相に依存しない場合と2局解析解だけ `global_minimum_for_this_phase_objective_proved=true`。

比較APIは各候補を別々に合わせ、段階100の安定な差計算で `log_likelihood1_minus0` を返す。両方が受理状態にならなければ `PhaseProfileConvergenceError`。異常なoptimizer出力も例外。未収束を0点に置き換えたり除外して精度を計算したりしない。正の値は合わせた候補1の条件付き尤度が高いことを表す。

## 適用範囲

未知振幅・SEFD・LO周波数差、区間内位相ドリフトは推定しない。画像尤度・p値・画像確率・実機較正の成功を返さない。現行Closure＋RMLを呼び換える部品ではない。全局共通Sの実データ保存も今回の変更に含まない。

## 再現

```bash
python tools/run.py tools.verify_gaussian_phase_profile --output outputs/phase-profile-reference
```

検証toolはリポジトリ側の実験用であり、導入済みpackageの通常CLIではない。既存出力は上書きしない。固定13条件、全開始点の数値、独立実Gaussian照合、3局格子、未収束対照と目的関数図を出力する。[段階103](../docs/reports/103-gaussian-phase-profile.md)に正式結果を記録する。
