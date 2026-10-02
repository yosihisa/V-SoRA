# 段階024：短露光のVDIF合成・Cas A形状と感度不足

- 作成日：2026-10-02
- 状態：有限条件の実装・検証完了。低感度ケースは失敗として記録
- 比較元コミット：2dc912c

## 読者向け概要

一回の積分を1秒に保ちながら、地球自転で変わるアンテナ間の見え方を集めます。各時刻の受信機gainは違っていても、その時刻ごとのClosureを作ってからRMLへ渡せます。8時刻の模擬VDIFからCas Aの相対形状を復元できました。ただし感度を高く仮定した条件です。感度を下げた試験では周波数差を測る基線が途切れ、最後まで画像化できませんでした。

## 1. 目的・対象範囲

別UTC原点の整列済み短露光を保持した合成、実VDIFを使う拡がったCas A模擬信号、未知gain/LO差、GUI・wheel検証。絶対flux・絶対位置・未知sample時計の復元、連続4時間の処理性能は対象外。

## 2. 完了条件

- UTC順に整列し、visibility・重み・channel・露光・flagを複素平均せず保持。
- 局・幾何・単位・周波数不一致、重複・重なる露光を拒否。途中失敗をincompleteとして保持。
- 8局のCas A模擬VDIFをrate推定から相対RMLまで処理し、結果と失敗条件を分ける。
- phase/amplitude独立測定数とoptimizer停止を表示し、情報不足を隠さない。
- source/wheelの全試験とGUI・checkout外合成CLIを確認。

## 3. 実際に行った作業

- `apps/imaging/src/vsora_imaging/synthesis.py`：spectral NPZ 2〜64入力、UTC変換・sort、軸一致・重複・overlap、入力SHA/rate/露光記録、partial→完了rename、CLI。
- `aligned.py`：積分区間の重複検査に使う公称積分長をmetadataへ保存。
- `rml.py`：phase/log amplitudeの独立測定数、amplitude情報の有無。
- `workflows/vdif_synthesis_validation.py`：8局の連続Gaussian sky＋独立受信機雑音からVDIF生成。未知sky設定を処理へ渡し、真値は生成と最終比較にだけ使用。
- GUI models/jobs/worker/static：合成画像の日本語入口、解析履歴の追加、複数NPZ、失敗理由の説明、測定数。
- synthesis/UI試験、実ブラウザ検証、`tools/verify_synthesis_installed.py`、`pyproject.toml`のvsora-synthesis。
- [規約](../../interfaces/closure-pipeline.md)、[学部生向け説明](../guide/07-closure-rml.md)、READMEを更新。

## 4. 検証条件・結果

Python3.12.3/NumPy2.5.1/SciPy1.18.0/Astropy7.2.2/Baseband4.3.0。8局・spread600m・RF1.42GHz・Fs2.048MHz・FFT8。4時間に8時刻を分散。一時刻は1.04秒VDIF、4ms×250のpilotと、再相関1秒。一局の使用露光は合計8秒で、4時間連続露光ではありません。

Cas A形状は参照画像、総flux1000Jyを生成側で仮定。連続周期Fourierのcolored Gaussian、sky相関は中心RF・中点で固定、station broadband delayは中点、RF delayは線形。帯域|f|≤0.25Fs、受理channel中心3個（幅256kHz）。narrowband sky近似の位相差概算≤0.00625rad。正確な公称sample時計を入力。未知station gainは振幅exp(uniform(-1.4,1.4))とrandom phase、各時刻のLOは概ね0,17.3,-11.7,26.1,8.2,-0.4,1.7,-3.1Hzに小さい乱数差。RMLは真のgain/sky/総Jyを入力しません。Gaussian事前240秒角、3初期値、最終2000反復。

| 条件・確認 | 観測結果 |
| --- | --- |
| 仮定SEFD1000Jy | 8/8時刻のrate推定・再相関成功。最大rate誤差0.01577Hz |
| 全Closure（重複あり） | phase922、log amplitude2032 |
| RMLの独立集合 | phase422、log amplitude398、合計820 |
| 相対画像 | 非負・有限、総量約1、ADC²から絶対Jyへ換算せず |
| 110秒角で比較 | 位置合わせ前NRMSE33.45%、平行移動後2.797%、形状相関0.99962 |
| 比較の平行移動 | y約37.03秒角、x約-24.67秒角。絶対位置を測定した値ではない |
| Closure χ²/測定数 | 0.7795。統計的p値ではない |
| optimizer | 3初期値とも2000反復上限。科学的収束とは記録しない |
| 仮定SEFD10000Jy | 2時刻完了、3時刻目でrate graph disconnected。合成画像なし |
| 低感度で完了した2時刻 | 各phase3、amplitude0。成功画像化として扱わない |
| source/wheel全試験 | 各121成功、3034既知deprecation warning、pip check成功 |
| Chromium実操作 | 解析履歴追加→2入力合成→相対画像、JS error0/外部通信0/390px横overflow0。中止成功 |
| checkout外wheel CLI | vsora-synthesis実行完了、ADC²、総量1、phase100/amp94 |

形状比較は110秒角に平滑化し、平行移動だけを合わせています。細かな画素構造の正確さ・絶対位置・絶対Jyは証明していません。SEFD1000Jyでは天体の自己雑音が無視できないこともあり、独立baseline/high-SNR近似のχ²は厳密な分布ではありません。

```bash
python tools/run.py workflows.vdif_synthesis_validation --sefd-jy 1000 --output outputs/stage024-vdif-casa-sefd1000
python tools/run.py workflows.vdif_synthesis_validation --sefd-jy 10000 --output outputs/stage024-vdif-casa
python tools/run.py pytest -q
python -m pytest -q
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser python tools/verify_ui_browser.py --output outputs/stage024-browser --analysis-manifest outputs/stage023-vdif-closure/input/manifest.json --clock-model outputs/stage023-vdif-closure/input/clock.json --synthesis-inputs outputs/stage024-vdif-casa-sefd1000/shot-00/pipeline/correlation/shard-00000.npz outputs/stage024-vdif-casa-sefd1000/shot-01/pipeline/correlation/shard-00000.npz
python tools/verify_synthesis_installed.py --inputs outputs/stage024-vdif-casa-sefd1000/shot-00/pipeline/correlation/shard-00000.npz outputs/stage024-vdif-casa-sefd1000/shot-01/pipeline/correlation/shard-00000.npz --output outputs/stage024-installed-check
```

[科学summary](../../validation/runs/stage024/summary.json)、[形状比較](../../validation/runs/stage024/comparison.png)、[低感度失敗](../../validation/runs/stage024/failure-summary.json)、[ブラウザ](../../validation/runs/stage024/browser-summary.json)、[合成画面](../../validation/runs/stage024/synthesis-screen.png)、[wheel入口](../../validation/runs/stage024/installed-summary.json)、[検証とwheel SHA](../../validation/runs/stage024/verification.json)。wheel5,422,068byte。原本VDIF/相関NPZはGit外outputs/stage024-*。科学summaryに入力SHAと生成条件を保存し、個人を含むローカルパスのmanifestを公開していません。

## 5. 制約・未解決事項

- 実RTL-SDR/自作アンテナのSEFDは未測定。1000Jyの仮定が実機で成立するとは言えない。
- 大容量連続観測、3秒積分、非線形LO変動とrateの更新、未知sample時計は未対応。
- channel間/時間/baseline自己雑音の全共分散、主ビームの局差、RFIは近似または未実測。
- 高SNR10の選別。長時間の露光数を増やすだけで低SNRを救済できる実装ではない。
- 旧profileのoverlapは最大有効露光から検査し、欠損を含む全区間supportを証明できない。
- Fourier行列128MiB上限。GUIは2〜32入力。Windowsブラウザ・WSLg実画面は直接未観測。

## 6. 次段階

アンテナの有効面積・雑音温度からSEFDを見積もり、数百ms〜3秒・channel幅とClosure情報数を比較する。rate/形状が測れる局配置と感度を判断し、低SNR処理と3秒/長記録の実装順を決める。
