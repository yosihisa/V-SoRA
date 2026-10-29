# 段階154：保存基線rateの採用maskだけを比べる

[レポート](../../../docs/reports/154-archived-rate-gate.md)、[全512組の基線候補・採否・群集計](reference.json)、[正式検証](verification.json)。16数値配列/完全log/初回失敗はGit外 `outputs/stage154-*-study` / `outputs/stage154-preparation`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.rate_gate_postselection_validation --archive outputs/stage147-source-study --output outputs/new-rate-gate-postselection
```

元147の保存summary/33配列が必要。元147のhelperで同じGaussian visibilityを再構成し、512学習fingerprint/1024 oracle行を照合する。新fit/新seed/新独立512組を追加しない。基線ごとの保存候補は局rate profileとは異なる。available/detected/rejectedは同じpower表の部分集合で、群差は記述だけ。独立eval残差の6MCSE検査は元147モデル試行を再利用し、3基線・群・source/nativeを独立追加観測として数えない。

nativeはcheckout外cwd/runner/PYTHONPATHなし、製品moduleは導入prefix。検証helper自体はcheckoutを要する。実機、全主経路、局graph選別の因果的分離、低SNR画像尤度の較正ではない。
