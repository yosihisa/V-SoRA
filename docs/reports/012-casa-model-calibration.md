# 段階012：Cas A shape較正と未知局応答の通し検証

- 作成日：2026-10-02
- 状態：完了（モデルを使うself-calibrationの整合確認）
- 比較元コミット：e0a64f6

## この段階の読み方

Cas Aを点源と決めつけず、広がった形を使って受信機応答を求めました。生成と較正に同じ形を使った整合試験であり、未知の空を独立に復元した証明ではありません。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・対象範囲

分解されたCas Aを点源として誤較正せず、shapeを較正モデルに使う。未知ADC利得・位相・delay・rateを含むIQ→VDIF→推定→再相関→IDI→画像を接続し、感度とpilot長の制約を確認する。

## 2. 完了条件

独立2点源式でモデル較正を検証。弱い参照baselineを別経路で補い、非接続・モデル不一致を拒否。8局16snapshotでCLEAN収束、共通110秒角のモデル比較NRMSE15%以内。失敗条件とpriorへの依存を記録する。

## 3. 実際に行った作業

- correlator calibrateに`--model-config`を追加。ICRS phase center一致と仮定fluxを記録。
- fringe探索を全baselineへ拡張。noise基準のpeak SNRで検出し、最大SNRのspanning treeで相対局応答を初期化。全局最小二乗で精密化。
- 固定coherence 0.25だけの拒否をやめ、低channel別SNRでも全帯域で強い検出を扱う。reduced noise chi square>3のモデル不一致は拒否。
- `workflows/casa_iq_calibration.py`：8局、4時間spanに16回の短いpilot。生成shapeを較正priorに使用することを明示。
- tests：独立2点源式、欠けた参照baseline、非接続、closure不一致、fluxと振幅の縮退を追加。

## 4. 検証条件・結果

```sh
python tools/run.py pytest -q
python tools/run.py workflows.casa_iq_calibration --output outputs/casa-low --receiver-sefd-jy 1000
python tools/run.py workflows.casa_iq_calibration --output outputs/casa-high --receiver-sefd-jy 10000 --pilot-seconds 1.024
```

仮定RF1.42 GHz、FS2.048 MHz、128channel、4ms積分。最大基線600mの8局、未知ADC振幅、delay、rate最大26.1 Hz、snapshotごとに未知位相。1GHz帯の参照shapeを1000 Jyへ規格化。実測SEFDではない。

| 条件 | SEFD1000 Jy | SEFD10000 Jy |
| --- | ---: | ---: |
| pilot/回 | 0.128秒 | 1.024秒 |
| 16回の実露光合計 | 2.048秒 | 16.384秒 |
| 平均visibility誤差/回 | 1.09～1.84% | 2.46～3.62% |
| 共通beam NRMSE | 0.01114 | 0.02265 |
| Pearson correlation | 0.999980 | 0.999930 |
| CLEAN model flux/prior flux | 0.98887 | 0.97677 |
| CLEAN | 収束 | 収束 |

初回star型探索では低noise条件の11回目で未検出。spanning treeで解消。SEFD10000 Jy＋0.128秒では1回目に非接続で失敗。pilotを1.024秒へ伸ばした条件では16回すべて検出した。4時間は**uv合成のspan**であり露光ではない。

独立2点源式で利得振幅1e-8相対、delay1e-13秒、rate1e-7 Hz以内。モデルfluxを真値の90%にすると局振幅が1/sqrt(0.9)倍になり、補正visibilityも900 Jyになる縮退を確認。段階012の全回帰 **55件成功**、既知Baseband warning553件。

記録：[低noise summary](../../validation/runs/stage012/low-noise-summary.json)、[高noise summary](../../validation/runs/stage012/high-noise-summary.json)、[低noise比較](../../validation/runs/stage012/low-noise-comparison.png)、[高noise比較](../../validation/runs/stage012/high-noise-comparison.png)、[短pilot失敗](../../validation/runs/stage012/short-pilot-failure.json)。raw VDIFはGit管理外`outputs/stage012-*`。

## 5. 制約・未解決事項

- **生成shapeとfluxを較正priorにも使っている。未知の空の独立復元の証明ではない**。画像一致はソフトの整合確認。独立較正のない絶対flux/位置の推定は縮退する。
- 仮定SEFD、FFT周期的な静止snapshot。連続の幾何変化、ADC drift、RFI、bandpass、主ビームは含まない。
- 1GHz帯の古いshapeが1.42 GHz実観測でも十分かは未確認。実際の較正・観測条件を測定する必要がある。
- 長pilotは推定を助けたが、全条件・全配置で同じ秒数を保証しない。解グラフと実SNRを確認する。
- 重みはtotal power近似、baseline間self-noiseの相関を完全には扱わない。chi square/SNRは形式的な実観測の誤検出保証ではない。

## 6. 次段階

周波数分解・flagsをFITS-IDIにも保持し、帯域平均前の情報を外部ソフトへ渡す。偏心点源を含む全視野の画像処理をさらに検証する。
