# 段階023：VDIFから短区間Closure＋RMLと日本語解析GUI

- 作成日：2026-10-02
- 状態：短区間の参照経路と有限条件の検証完了
- 比較元コミット：aab6bfc

## 読者向け概要

生のVDIFから、sample時刻と幾何を合わせ、未知LO差を短pilotで推定し、IQを補正して再相関し、Closureから相対画像を作る経路をつなぎました。高精度な局gainも既知の天体fluxも入力しません。日本語GUIからファイルを指定できます。現在は1秒以内の短区間で、実Cas Aの長時間合成は次に進める課題です。

## 1. 目的・対象範囲

VDIF/時計モデル→整列pilot→モデル不要rate→IQ再相関→Closure→相対RMLの5工程。単位・時刻・局順・原本識別・途中失敗・配布wheel・GUIまで対象とする。未知ADC時計の復元、3秒整列、長時間合成、実装置は対象外。

## 2. 完了条件

- 実VDIFを使う連続Gaussian点源試験でrate誤差0.05Hz未満、有効phase/amplitude Closure、非負の総量1画像。
- sample時計・RF幾何・rateを併用し、ADC²をJyと偽らない。
- 局順・UTC原点・finite値・rate時間範囲を確認し、外挿を自動で行わない。
- 途中失敗はpartial/incomplete、最終outputは作らず、既存outputは上書きしない。
- 日本語GUIとcheckout外wheelのCLI/GUIでVDIF解析を実行できる。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/closure_pipeline.py`：5工程、原本全体SHA-256、manifest/clock/観測設定SHA、設定コピー、progress、partial→完了rename。
- `aligned.py`とCLI：1〜256積分・span1秒。rate-only補正を実際に読むsampleのphysical timeで適用。geometryの事前検査をpartial作成前へ移した。
- `rate.py`：production profileにclock/phase center整列、局ID、UTC、SHAを要求。既に除去したrateと残差rateを合成。局・原点・期間・基準時刻を検査。
- 観測configとsimulator：source.model=unknownなら既知総fluxを省略。unknown skyからのtruth生成は拒否。
- `workflows/vdif_closure_validation.py`：連続帯域制限Gaussian信号、実VDIF、幾何・未知gain/rate、整列時計を使う再実行可能な検証。
- integration/config/UI試験：5工程、未知flux、profile不一致、上書き拒否、範囲外でのincomplete。
- 日本語GUI：manifestとclockを指定する「VDIF解析」、5工程と相対画像。入力はWSL内のJSON、VDIFをブラウザへ送らない。
- `tools/verify_ui_browser.py`：実VDIF解析のブラウザ試験。`tools/verify_closure_installed.py`：checkout外の新CLI/GUI検証。
- `pyproject.toml`：`vsora-closure-session`。[規約](../../interfaces/closure-pipeline.md)と[入門](../guide/07-closure-rml.md)を更新。

## 4. 検証条件・結果

Python3.12.3、NumPy2.5.1、SciPy1.18.0、Astropy7.2.2、Baseband4.3.0。4局、RF1.42GHz、Fs2.048MHz、270 frame/局＝1,105,920sample＝0.54秒。FFT32、pilot2ms×256＝0.512秒、開始offset0.002秒、画像積分0.3秒。

生成信号は周期Fourierによる連続帯域制限Gaussian点源1000Jyと独立受信機雑音SEFD10000Jy。帯域|f|≤0.25Fs、受理|f|≤0.2Fs。skyのbroadband delayは中点固定、RF delayは線形変化。中点近似の最大位相差概算2.34e-5rad。時計は正確な公称値・開始差0を与える。真のgain振幅 `[0.4,3,1.5,0.75]`、位相 `[0,0.7,-1.1,2]`、rate `[0,17.3,-11.7,26.1]`Hz。処理へ渡す観測設定はsource=unknown、総fluxなし。

| 確認 | 観測結果 |
| --- | --- |
| 推定rate最大誤差 | 0.009519Hz |
| 相関単位 | ADC²を維持 |
| Closure | phase52、log amplitude26がSNR10条件を満たす |
| 相対画像 | 有限・非負、総量1、peak[16,16] |
| Closure χ²/測定数 | 約0.611。p値ではない |
| 絶対Jy・絶対位置 | 未測定と明記。中心peakは表示上の制約と生成点源の比較 |
| profile期間外 | 1秒積分は0.512秒pilotの外で拒否。partialに先行2工程のみ記録 |
| 全試験 | source115件、wheel再導入環境115件成功 |
| ブラウザ | Chromium153、VDIF指定→5工程→相対画像、日本語font、JS error0、外部通信0、390px横はみ出し0 |
| checkout外wheel | 5つの新/GUI入口help、VDIF解析CLIとGUI完了。ADC²、総量1、有効Closureを確認 |

3034件の既知deprecation warning（BasebandのVDIF読取回数増加とStarlette/httpx）。初回wheel再導入試験はGUI試験のsource_root依存で113成功/2失敗。試験側のrunner場所を実際のtestファイルから指定するよう修正し、115成功へ再実行。checkoutの検証workflowを呼ぶGUI試験も含むため、加えてcheckout外の実CLI/GUIを個別に確認した。

最初の`--no-build-isolation`はverification環境にsetuptoolsがなく失敗。独立build環境でwheel作成・再導入し、pip check成功。wheelは5,417,009byte、SHA-256 `b912d18ee7a3f5eae3a36f3e6b486ccfa0676f4cd6a1ad9ffc995ae60e3b765e`。生成物はGit外`outputs/stage023-wheel/`。

```bash
python tools/run.py workflows.vdif_closure_validation --output outputs/stage023-vdif-final
python tools/run.py pytest -q
python -m pytest -q
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser python tools/verify_ui_browser.py --output outputs/stage023-browser --analysis-manifest outputs/stage023-vdif-closure/input/manifest.json --clock-model outputs/stage023-vdif-closure/input/clock.json
python tools/verify_closure_installed.py --manifest outputs/stage023-vdif-closure/input/manifest.json --clock-model outputs/stage023-vdif-closure/input/clock.json --output outputs/stage023-wheel-check
```

詳細：[科学summary](../../validation/runs/stage023/summary.json)、[相対画像](../../validation/runs/stage023/rml.png)、[ブラウザ](../../validation/runs/stage023/browser-summary.json)、[解析画面](../../validation/runs/stage023/analysis-screen.png)、[wheel](../../validation/runs/stage023/wheel-summary.json)。原本VDIFと内部NPZはGit外`outputs/stage023-vdif-*`、summaryにSHA・byte数・設定・条件を保存。公開記録にローカルパスを含むmanifestコピーは入れていない。

## 5. 制約・未解決事項

- 4局・一点・0.3秒の一積分。Cas Aの形状復元、複数時刻の合成と長時間性能を検証した結果ではない。
- 整列chunk1秒以内・600m。0.1〜1秒pipeline画像積分。実用予定の3秒整列と連続処理は後続段階。
- supplied linear clockで、未知時計・非線形LO変動を同時に解かない。共通LO差の絶対値も測らない。
- 低SNR、自作アンテナ主ビーム差、baseline固有誤差、RFIの実測性能に未対応。filtered FFT雑音相関を完全には扱わない。
- 原本全体SHAは長い観測で読取時間を要する。処理速度・必要メモリの実観測規模評価は未実施。
- RMLは局所解や反復上限がある。工程完了と科学的収束を区別する。FITSの位置原点とfluxは相対表示の約束。
- Windowsブラウザ/WSLg実デスクトップ、実RTL-SDRは直接未確認。

## 6. 次段階

短露光を複数時刻へ分散した実VDIF模擬観測を合成し、未知gainのCas A形状をRMLで復元する。長時間入力のstream、3秒積分の時計/幾何整列、rateの更新、GUIの複数session入力へ進む。
