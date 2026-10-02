# 段階021：Closure＋RMLのCPU参照実装と日本語GUI

- 作成日：2026-10-02
- 状態：参照実装と有限条件の検証完了。Cas A最適化の上限到達は継続課題
- 比較元コミット：2ec767b

## 読者向け概要

局の利得を正確に測れない条件で、Closureに合う非負画像を探すRMLを作りました。画像の総量を1に固定し、絶対Jyと位置原点を測ったことにしません。正解の生成画像を事前画像に使わず、汎用Gaussianから復元し、局所解・感度・事前条件の影響も記録します。

## 1. 目的・対象範囲

小規模CPUのClosure RML、解析勾配、独立Closureと全共分散、ADC²入力と相対FITS、短露光の模擬観測、日本語GUIを対象とする。LO/sample時計は補正済みの前提。実VDIF画像化は次段階。

## 2. 完了条件

- 位相の周期性を使う初期探索と最終Gaussian評価の勾配が独立有限差分と相対1e-6以内で一致。
- 任意局利得を加えても、同じ候補画像の目的関数・勾配が一致。
- 独立三点源試験で非負・総量1を保ち、Closure χ²/測定数0.2未満。
- 模擬二点源・環の110秒角での形状誤差が20%未満。Cas Aは感度・事前条件依存を評価し、未収束を明記。
- ADC²をJyに置き換えず、GUIからRMLを実行して画像と数値を確認。

## 3. 実際に行った作業

- `apps/imaging/src/vsora_imaging/rml.py`：直接Fourier演算子、独立Closure共分散、解析勾配、非負探索、entropy/TSV、弱い中心条件、複数初期値、CLIと相対FITS。Fourier行列は128MiBまで。
- `apps/imaging/src/vsora_imaging/experiment.py`：全観測時間と短露光を区別した模擬観測、未知局利得、比較時だけ真値との平行移動登録、summary/図。
- `workflows/closure_rml_validation.py`：SEFD仮定と短積分、生成モデル・noise・seed・事前幅の比較。
- `apps/imaging/tests/test_rml.py`：softmaxと直接強度の勾配、局利得不変性、三点源、低SNR拒否、ADCとFITS単位/checksum。
- GUIのmodels/jobs/worker/static・server試験：日本語RML画面、相対単位、χ²・停止・露光・登録前後誤差。履歴をcreated_utc順へ修正。
- `tools/verify_ui_browser.py`：RML実操作・画像表示を追加。mobileのgrid最小幅を修正。
- `pyproject.toml`：`vsora-rml`。入門ガイドを追加。

初期実装では強い中心拘束とlog画素探索により局所解に止まり、三点源の適合条件が失敗しました。中心を弱め、非負強度を直接探索しました。さらに正規化前の画素総量が自由に拡大すると停止判定が緩くなるため、その不要なscaleを固定するpenaltyを追加。最終単位flux画像とは別の探索パラメータの規約です。修正前結果は`outputs/stage021-*`の旧条件として残し、本レポートの表には最終条件を使用します。

## 4. 検証条件・結果

Python3.12.3、NumPy2.5.1、SciPy1.18.0。1.42GHz、Fs仮定2.048MHz、8局、最大600m、4時間の間に16snapshot。各snapshotは0.3秒または3秒、総露光4.8/48秒。32²・16秒角。基線SNR10以上、仮定SEFD10000Jy、flux1000Jy。一次元Gaussian雑音を各実/虚部へ独立に追加。IQ生成ではないためself-noiseなし。局gainの振幅はexp(uniform[-1.8,1.8])、位相はuniform[-π,π]で時刻ごとに変更。IERS status2は予測値。

RMLのGaussian事前画像はFWHM240秒角（比較160）、entropy0.01、TSV0.0001、中心penalty0.1、3初期値、初期周期探索最大300回＋最終2000回。生成画像は目的関数へ渡していません。

| 条件 | 登録前NRMSE | 登録後NRMSE | χ²/測定数 | 選択した探索 |
| --- | --- | --- | --- | --- |
| 二点源、雑音なし、0.3秒 | 詳細summary参照 | 2.53% | 0.0341 | 停止条件到達 |
| 環、雑音なし、0.3秒 | 詳細summary参照 | 6.97% | 約0.0015 | 2000回上限 |
| Cas A、雑音あり、0.3秒 | 46.8% | 34.2% | 0.306 | 2000回上限 |
| Cas A、雑音あり、3秒 | 詳細summary参照 | 8.73% | 0.644 | 2000回上限 |
| Cas A、3秒、prior160 | 詳細summary参照 | 5.14% | 0.654 | 2000回上限 |
| Cas A、3秒、seed22 | 詳細summary参照 | 5.29% | 0.673 | 2000回上限 |

位置合わせは比較時だけ、総量1の基準と共通110秒角Gaussianを使い、平行移動量を明示。SNRcutと探索自由度を含むため、χ²はp値ではありません。上限到達を収束としません。Cas A画像は2017年の1GHz帯参照形状からの模擬入力で、実1.42GHz観測ではありません。

```bash
python tools/run.py pytest -q
python tools/run.py workflows.closure_rml_validation --model casa --noise --integration-s 3 --max-iterations 2000 --output outputs/stage021-casa-3s
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser python tools/verify_ui_browser.py --output outputs/stage021-browser-fixed
```

全試験105件成功、874件の既存依存deprecation warning。Chrome153で点源・RML・quality・中止を実操作。RML画面の登録後誤差2.94%、日本語font表示、JS error0、外部通信0、390pxの横はみ出し0。最初のブラウザ試験はmobileのgrid幅で失敗し、修正後に再実行。Windows側ブラウザとWSLg desktopは直接確認していない。

[詳細記録](../../validation/runs/stage021/)に各条件summary/図とブラウザ記録を保存。大きな相関NPZ・相対モデルはGit外の`outputs/stage021-*`。summaryに入力SHA-256・設定・露光・停止状態を保存。

## 5. 制約・未解決事項

- 小規模の直接Fourier CPU実装。GPU、長時間stream、外部RMLソフトの比較は未実施。
- LO/sample時刻補正済みを仮定。積分中の相関損失と未知時計推定の問題は残る。
- 高SNR Gaussian、baseline独立noiseの近似。低SNR bias、self-noise、channel間相関、主ビーム差に未対応。
- 非凸・初期値/事前条件依存。Cas Aの探索は上限到達が残り、有限条件の形状一致だけで実観測成功とはしない。
- 絶対fluxと絶対位置は測れない。FITS座標は表示基準。正規化・移動登録で消えた情報を実測と誤認しない。
- 16短露光の疎な模擬実験で、4時間連続収録の感度ではない。

## 6. 次段階

天体の絶対振幅・位相を既知としない短pilotの局間LO差推定を作る。IQ補正・再相関・Closureを接続し、unknown gainを保持した実VDIFからRMLへの参照経路を作る。長時間・低SNR・事前条件の再評価とGUIの実観測入口へ進む。
