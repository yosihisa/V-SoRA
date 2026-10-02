# 段階007：未知の遅延・位相・rate・利得の推定

- 作成日：2026-10-02
- 状態：完了（既知モデル、一様格子、一定局応答の参照実装）
- 比較元コミット：488d3f2

## この段階の読み方

受信機ごとの振幅・位相・時間差・位相の回転速度を未知の値として与え、既知の天体から求め直しました。基準天体の明るさが既知という条件の試験です。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・対象範囲

既知の補正値を相関器に与える段階から進め、周波数・時間分解visibilityから未知の局応答を推定する。較正点源とCas Aの模擬観測を分け、推定した補正がtargetにも有効か確認する。

## 2. 完了条件

独立に注入した局応答をnoiseなしで回収、noise/flag/参照局変更でも所定誤差内。未検出、振幅縮退、探索範囲超過、外挿を明示。5乱数条件でCas Aの補正後visibility誤差3%以内。全テスト成功。

## 3. 実際に行った作業

- `apps/correlator/.../fringe.py`：参照局baselineの2D FFT探索、解析Jacobianを用いた全局複素最小二乗、逆分散の伝搬、範囲を持つ較正JSON。
- `packages/formats/.../spectral.py`：time/channel/baseline NPZ。平均前の位相情報を保持。
- `workflows/fringe_validation.py`：8局、既知1000 Jy点源から推定し別noiseのCas Aへ適用。5seed。
- `interfaces/spectral-and-calibration.md`：単位、符号、alias、ゲージ、適用範囲を定義。[CASAの公式fringefit説明](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.calibration.fringefit.html)を参考にした。CASAソースはコピーしていない。
- fixtureの局位置listをstation辞書に包み忘れた初回workflowを修正し、再実行した。

## 4. 検証条件・結果

```sh
python tools/run.py pytest -q
python tools/run.py workflows.fringe_validation --output outputs/fringe --seeds 5
```

8局、64channel、間隔32 kHz、64時刻、間隔20 ms、span1.26秒。位相最大2.2 rad、delay最大3.1 μs、rate最大6.2 Hz、振幅0.8～1.2を独立注入。visibilityのreal/imagそれぞれ100 Jyの解析noiseと一部weight=0を使用。delay曖昧周期31.25 μs、rate曖昧周期50 Hz。

| 5seedでの指標 | 観測範囲 |
| --- | --- |
| delay最大誤差 | 0.249～0.498 ns |
| rate最大誤差 | 0.000375～0.000802 Hz |
| 利得振幅最大相対誤差 | 0.047～0.143% |
| 補正前の平均Cas A visibility相対誤差 | 1.001～1.004 |
| 補正後の平均Cas A visibility相対誤差 | 0.903～1.203% |

noiseなしの独立4局forward testではdelay誤差1e-14秒以内、rate誤差1e-8 Hz以内。参照局を2へ変更したnoise test、weight補正、未検出・未識別・外挿拒否を含め **39件成功**（追加6件）。Baseband既知warning37件。

詳細：[summary](../../validation/runs/stage007/summary.json)、[較正JSON](../../validation/runs/stage007/calibration.json)、[比較図](../../validation/runs/stage007/comparison.png)。NPZ cubeはGit管理外`outputs/stage007-fringe-v2`。

## 5. 制約・未解決事項

- この段階の誤差はvisibilityへ解析的に注入。LOずれを持つ連続IQからの検証は次段階。
- 既知flux/model、一定局応答、一様格子、各局と参照局間の検出を要求。参照baselineが弱い際の別経路探索は未実装。
- 模擬較正点源とtargetは同じ短時間・同方向条件。異時刻・異方向の転送は未検証。
- alias外の真値は内部だけでは区別できない。粗いtimestamp等の外部情報が必要。
- noiseモデルは実測SEFDに基づかない。検出指標は実観測の誤検出率を保証しない。
- 分散delay、bandpass、方向依存、非線形clock drift、既に平均で失われたcoherenceは未対応。

## 6. 次段階

IQに未知のLO/rateを注入し、短時間FX→周波数分解保存→推定→補正後平均を接続する。長いIQをメモリ全読込みせず処理する準備も進める。
