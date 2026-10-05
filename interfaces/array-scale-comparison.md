# 既知天空での配置尺度比較

`vsora_simulator.array_shape.population_closure_signature(v, pairs, total_flux_jy)` は有限標本の雑音を推定する処理ではなく、既知の母集団visibilityの点源からの差をまとめる。

- 入力：有限複素baselineベクトル、対応する整数ペア `i < j`、正の既知総flux。最大8局。
- phaseは既存closure designをbaseline位相へ適用し、主値−π〜πへ折り返す。logampは自然対数振幅へ適用する。
- `|V| <= total_flux * 1e-12` は数値的な除外。必要な辺を含むclosureを無効にし、値は `null` とする。これはSNR判定ではない。
- 点源の母集団closureはphase/logampとも0。3局にはclosure amplitudeがなく、RMSは `null`。
- `*_rms_from_point` と `*_maximum_abs_from_point` は有効な全行の記述量。行の重複・共有baselineを含み、独立情報量や尤度には変換しない。
- 局別の一定複素gainはphase/logampで相殺する。有効行の集合が同じ場合に比較する。相関flux比はgain不変な観測量ではなく、既知のモデルを総fluxで割ったもの。

`workflows.array_scale_validation` は8局・3配置・6最大距離の単一時刻を比較する。天体電圧のGram行列とdirect visibilityを照合し、既存 `known_bispectrum_moment_scale` で3SEFD×2積分長を計算する。U3尺度は `|E U3| / sqrt(E |U3-E U3|²)`。全triangleを独立とは扱わない。

最大投影基線から得る `206264.806... / |b_uv|` arcsecはfringe周期で、復元beamや画像の分解能の実測ではない。既知形状の点源との差、相関flux、U3尺度を並べても、画像復元成功や最適配置は判定できない。詳細条件と入力識別情報は出力JSONに保存する。

## 配布済みの計算入口

`vsora_simulator.array_scale.run(output)` と `python -m vsora_simulator.array_scale --output ...` で同梱設定・画像を使用する。既存の `workflows.array_scale_validation` は互換入口。科学JSONは従来と同一で、固定設定の識別SHAも維持する。

GUIの配置比較はこのAPIを直接呼び、実行元の所属と同梱設定SHAを `validation/execution-origin.json` に保存する。ホスト上の実パスは公開記録に含めない。その他の動作検証のリポジトリ要件は継続する。
