# 段階051：pilotの時間散乱の条件付き診断

- 作成日：2026-10-04
- 状態：完了（受動診断CLIと固定モデル検証の範囲）
- 比較元コミット：e3ba4dd

## 読者向け概要

短い相関を時間方向へ並べ、周波数差の補正後にも平均値から大きく散らばるか調べます。雑音の寄与を仮定モデルで引きます。散らばりは位相変動だけでなく、振幅・天体・雑音モデルの変化でも起きるため、実機のcoherenceや画像品質と断定しません。

## 1. 目的・対象範囲

保存pilot NPZと任意の保存rate profileを読み、基線別の時間power・平均power・差を出す受動診断CLIを追加します。共通FFT数と局powerが保存された32〜8192cell、選択した一channelを対象とします。profile補正はcell中心での位相回転です。

## 2. 完了条件

既知Gaussian電圧の固定・周期位相・振幅変動・弱信号で数式の期待値を確認。局gain変換、rate符号、負のpower・1超の比、情報不足・品質flag・二重補正・外挿拒否、入力識別と上書き拒否を確認すること。段階039の模擬VDIFをFFT数保存付きで再相関し、正解を入力せず対照と高速変動を診断すること。source/wheel全回帰、匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/time_scatter.py`：power推定API、native入力診断、cell中央のprofile回転、未判定理由、閉じた入力/profileのSHA256・stat確認、JSONの上書き拒否。
- `pyproject.toml`：配布CLI`vsora-time-scatter`。
- `apps/correlator/tests/test_time_scatter.py`：32件の式・符号・gain・拒否条件・Gaussian・実VDIF試験。
- `workflows/time_scatter_validation.py`：4モデル×2048試行、同じGaussian電圧から局power・相関・雑音分散を推定。
- `workflows/time_scatter_replay.py`：段階039の閉じた模擬VDIFを再相関し、保存profileを用いた診断を比較。
- `tools/verify_time_scatter_installed.py`：checkout外で配布console CLIとAPI、固定source結果の一致、上書き拒否を確認。
- [入力・式の規約](../../interfaces/pilot-time-scatter.md)、[利用ガイド](../guide/07-closure-rml.md)、索引、小容量記録。

全cellの条件を確認し、不適格なcellを暗黙に除外しません。差引power・比は負や1超を切り詰めず、時間powerが非正なら基線の比を未判定にします。単位はADC^4またはJy^2で、振幅比とは異なります。

## 4. 検証条件・結果

### 対象検証とGaussian電圧

最終対象32件成功、警告640件、2.91秒。一定/線形rate回転の符号、元配列の不変更、固定gainでのpower比不変、負power、1超の比、品質・集合・露光差・範囲・二重補正・入力変化・上書き拒否を確認しました。32個の模擬VDIF相関も診断しました。

4条件それぞれ2048試行、128時間cell×32独立電圧標本×4局。共通点源の電圧分散0.3・各局の独立雑音分散1（任意単位）、弱信号は点源分散0.001としました。これは正規化した局間coherenceの値ではありません。周期例は第4局へ位相振幅0.8rad、振幅例は1±0.5の正弦を加えました。正解は検証だけへ使い、power推定に渡していません。

時間power・平均power・excessのensemble平均は全基線で固定6SE基準内。比の不偏性や観測の6σ信頼区間を検証した意味ではありません。

| 条件 | 3種類power平均の最大差 / SE | 時間power非正の割合（基線範囲） |
| --- | ---: | ---: |
| constant | 1.399 | 0.0〜0.0% |
| periodic_phase | 2.358 | 0.0〜0.0% |
| amplitude | 2.032 | 0.0〜0.0% |
| weak | 1.876 | 48.2〜53.0% |

一定条件でも比が1超となる試行が約半数あります。弱信号は時間power非正が約48〜53%で、その比は計算対象外です。Gaussian workflowの実測wall5.34秒・最大RSS101800KiB、1thread設定。

### 固定模擬VDIFの再相関

段階039の同じGaussian sky/noiseの対照と32Hz位相変動の閉じたVDIFを再利用。2ms×1500cell、FFT32、各cell128FFT、中央RF1420MHz。新しい共通FFT数保存を得るためpilotを再相関し、対照の保存一定rate・高速例の保存線形rateをcell中央で回転しました。

対照のpower比は0.9852469〜1.0308393、高速例は0.7261951〜0.9873786。最小値はST03–ST04で約0.726。診断にskyや位相揺れの正解は渡していません。比較・合否には模擬対照を使っています。これは実機で得られる対照ではありません。旧pilotは共通基線FFT数がなく、推測して補わず未判定にしました。

再相関のwall58.72秒・最大RSS229060KiB、1thread。初回は検証起動方法を修正し、次の実行ではnative露光が時間×基線配列であることへの未対応を検出しました。両形式へ対応し、基線露光差は拒否する試験と実VDIF試験を追加して再実行成功しました。失敗ログもGit外に保持しています。

### 全回帰・配布

source433件成功、警告23952件、420.08秒。installed433件成功、警告23952件、423.66秒。試験除外なし。source→checkout外installed CLI/API→installed全回帰の順で実施。既存Baseband/NumPy等のdeprecation警告を含みます。pip check成功。Python3.12.3・NumPy2.5.1・SciPy1.18.0・Astropy7.2.2・Baseband4.3.0・Pytest8.4.2。

配布CLIとAPIは固定source結果と全JSON一致、入力/profileのSHA256一致、再実行の上書きを拒否しました。wheel5475521bytes、SHA256 `c9c597c657d0ab132af4162b064ce2553d51c3d3baf4bbf26b705c890a5cc920`。

[Gaussian記録](../../validation/runs/stage051/gaussian.json)、[VDIF比較](../../validation/runs/stage051/vdif-replay.json)、[配布CLI/API](../../validation/runs/stage051/installed-api.json)、[回帰・資源・wheel](../../validation/runs/stage051/verification.json)。大容量NPZ・完全ログ・wheelはGit外`outputs/stage051-*/`。元VDIFは段階039のGit外archiveと入力識別情報を用います。

```bash
python tools/run.py workflows.time_scatter_validation --output outputs/new-time-power-check
python tools/run.py workflows.time_scatter_replay --archive outputs/stage039-periodic --output outputs/new-pilot-replay
```

2つ目は既存の閉じた段階039archiveが必要です。

## 5. 制約・未解決事項

公称共通FFTを独立proper Gaussian電圧として扱い、時間cell同士も独立と仮定します。同じpilotで推定したprofileの依存性・選別、FIR、ADC、弱信号の比の信頼区間は未校正。cell内の平均化損失・alias・UV変化も残ります。ratioの値から実機coherence、位相だけの揺れ、画像品質を断定しません。RML重み・自動停止基準は変更していません。

## 6. 次段階

保存pilot診断の日本語GUIを追加し、状態と低SNRの未判定を表示します。低SNRで使えるClosure統計も引き続き検討します。
