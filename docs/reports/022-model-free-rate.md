# 段階022：skyモデルを使わない短pilot周波数差推定

- 作成日：2026-10-02
- 状態：有限条件の参照実装・検証完了
- 比較元コミット：a12d103

## 読者向け概要

未知の受信機利得をClosureで消しても、積分中に相関が消える問題は残ります。短い相関を時間順に並べ、その位相が回る速さだけを推定しました。天体の正しい振幅や位相を与えず、channelごとの未知の複素相関は未知のまま残します。推定した速さでIQを補正して再相関すると、0.3秒積分でClosureを使える状態へ戻せました。

## 1. 目的・対象範囲

既知skyモデルや絶対利得較正を要求しないLO rate推定、局間整合性、IQ補正後の短積分Closureを対象とする。sample時刻は整列済み、sky/利得は1秒以内で一定、rateは一定と仮定する。Windows収録、ADC時計推定、VDIFの接続、RML画像化との結合は本段階に含めない。

## 2. 完了条件

- 未知のbaseline/channel位相でも4局rateを0.02Hz以内で推定する。
- 未知局gainを変えても推定rateが1e-7Hz以内で一致する。
- 直接reference基線が欠けても連結graphから推定でき、非連結・探索外・不均一cadenceを拒否する。
- 雑音のみ20seedをrate検出成功にしない。
- 実IQの3seedで最大rate誤差0.05Hz未満、再相関のcoherence0.9〜1.1、Closure RMS0.2未満。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/rate.py`：1秒以内・8時刻以上のpilotでbaseline rateを探索。baseline/channelごとに未知複素定数を持ち、時間方向の傾きだけを推定する。FFT候補、連続探索、解析微分による精密化。連結graphの重み付き最小二乗で局rateへ変換する。
- `apps/correlator/tests/test_rate.py`：任意channel位相・未知gain・欠損graph・探索/時刻拒否・雑音だけの試験。
- `workflows/closure_rate_validation.py`：連続Gaussian IQ、短pilot、推定rateでIQ補正、0.3秒FXとClosure、数値/図。
- `pyproject.toml`：`vsora-rate`。spectral NPZからrate-only JSON、入力SHA-256と時刻原点を保存。
- GUIのmodels/jobs/worker/HTMLとserver試験：日本語の「skyモデルを使わない周波数差推定・IQ補正」を追加。

初期の連続スカラー探索はgain変更時に1.26e-7Hzの丸め差で厳しい一致条件を外れた。閾値を緩めず、解析一次/二次微分のNewton精密化を追加して再検証した。

## 4. 検証条件・結果

Python3.12.3、NumPy2.5.1、SciPy1.18.0。pilot0.512秒、Fs2.048MHz、4局、FFT32、1ms相関×512時刻。常時共通Gaussian点源1000Jyと局別独立Gaussian受信機雑音（仮定SEFD10000Jy）。局gain振幅 `[0.4,3,1.5,0.75]`、位相 `[0,0.7,-1.1,2]`rad、rate `[0,17.3,-11.7,26.1]`Hz。再相関は0.3秒、32channel。skyの振幅/位相やgainの真値を推定器へ渡していない。

```bash
python tools/run.py pytest -q
python tools/run.py workflows.closure_rate_validation --output outputs/stage022-rate --seed 22
python tools/run.py vsora_correlator.rate --input outputs/pilot.npz --output outputs/rate-only.json --max-rate-hz 100
```

| 条件 | 結果 |
| --- | --- |
| 任意channel sky位相 | rate誤差0.02Hz条件を満たす |
| gain変更 | rate差1e-7Hz条件を満たす |
| 欠損graph | reference直接2基線を除いても推定、reference切断で拒否 |
| 雑音だけ20seed | 全条件で非検出。実環境の誤検出率ではない |
| 実IQ seed22 | rate誤差0.01182Hz、coherence中央値3.41%→100.45% |
| seed22のClosure | 有効phase0→128、log amplitude0→64。補正後RMS0.0907rad/0.0861 |
| 実IQ seed23/24 | 0.05Hz・coherence0.9〜1.1・Closure RMS0.2条件内。詳細summary参照 |

全試験111件成功、874件の既存依存deprecation warning。GUIの新検証は実subprocessでsummaryまで確認。段階021のChromium操作試験は本段階で再実行していない。実装置・RFI・非線形位相雑音は未実施。

詳細：[seed22](../../validation/runs/stage022/seed22-summary.json)、[seed23](../../validation/runs/stage022/seed23-summary.json)、[seed24](../../validation/runs/stage022/seed24-summary.json)、[図](../../validation/runs/stage022/rate.png)。大容量IQはメモリ内、内部FX結果はGit外の`outputs/stage022-rate/`。保存した`corrected-spectral.npz`は内部検証用arrayで、共通metadataを持つ標準開発profileではない。

## 5. 制約・未解決事項

- rateは基準局に対する差だけ。全局共通の絶対周波数差は測れない。振幅・sky位相は較正しない。
- 各短pilotでskyとgainを一定と置く。天体のphase急変、gain変動、非線形LO drift、ADC sample rateずれを同時に解くものではない。
- coherence検出は未知channel位相を残すため、既知skyの全帯域coherent検出より弱い場合がある。少なくとも使える基線graphが連結する必要がある。
- 検出SNR8とnoise peak指標8を使うが、探索回数を含む厳密な誤検出確率の較正は未実施。雑音20seedの非検出は有限確認。
- thermal独立baseline/channel近似。共有sky雑音やADC補間由来相関に未対応。
- 一様時刻、8時刻以上、pilot1秒以内、探索は時間Nyquist未満。真のrateがalias範囲外でないというhardware側の情報も必要。
- 本段階では補正後coherenceを限定bandpass条件でchannel平均して比較した。実天体の複素channel平均を一般に推奨するものではない。

## 6. 次段階

VDIF・ADC²・未知sky/gainのまま、pilot推定→IQ補正→短積分相関→Closure→RMLを接続する。sample時計と幾何delayの補正を維持し、metadataと原本識別情報・適用時刻・failureを保存する。GUIからの実データ解析入口へ拡張する。
