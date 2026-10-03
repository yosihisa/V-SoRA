# 段階038：線形rateの日本語GUIと区間列

- 作成日：2026-10-03
- 状態：完了（模擬VDIFの解析経路と表示の範囲）
- 比較元コミット：ed560cb

## 読者向け概要

「VDIF解析」「区間列解析」で、初期値の一定rateか、滑らかな線形rateを選べるようになりました。線形モデルでは局ごとの周波数差の傾きと近似誤差を表示します。実際に測ったpilotの中だけでモデルを使い、区間の間を測定した扱いにはしません。

## 1. 目的・対象範囲・完了条件

段階037の線形IQ補正を観測者がGUIで使える入口を作ります。区間列にも選択を引き継ぎ、矛盾した入力を拒否し、モデルが解けない場合を日本語で表示します。完了条件は実子プロセス・installed Chromium・source/wheel・独立区間列CLI・記録・匿名コミットです。実機の位相安定性とCas A画像忠実度は対象外です。

## 2. 実際の作業・変更ファイル

- `sequence.py`：constant/linearを各windowへ渡し、parent summaryにモデルを保存。CLI `--rate-model` を追加。
- UI `models.py`：モデルの値を制限し、線形モデルと一定rate整合必須の同時指定を拒否。
- `static/index.html`、`static/app.js`：選択欄、傾き・近似σ・model χ²・計算coherenceを日本語表示。線形選択時は一定モデルの必須checkboxを外して無効化。補正前の変動診断と、選択した補正を区別して説明。
- `worker.py`：pilot内にモデル線を描画し、情報不足・モデル不整合などを日本語へ変換。
- UI tests、`workflows/linear_sequence_validation.py`、`tools/verify_linear_ui.py`、既存独立sequence CLI toolのモデル指定、guide06/07、interface、記録を追加。

線形モデル自身の適合条件は常に確認します。「変動検出」は補正前の一定rate仮定の診断として残します。線形補正を実施しても、周期的位相揺れを測れたという表示にはしません。

## 3. 検証条件・結果

### 3区間の物理IQ→VDIF

4局、1.42GHz、2.048Msample/s、点源、仮定SEFD10000Jy、固定未知gain、seed38、1.6秒の模擬記録を生成。仮定rate傾き[0,1,-.5,1.5]Hz/sを入れました。補正には生成値を渡さず、0.512秒pilotを3回測定し、各0.3秒の相関を一つの相対RMLへ入力しました。

| 区間 | 最大rate誤差 Hz | 最大傾き誤差 Hz/s | model reduced χ² |
| --- | ---: | ---: | ---: |
| 1 | 0.02518 | 0.68069 | 1.400 |
| 2 | 0.05240 | 0.29729 | 0.842 |
| 3 | 0.03838 | 0.31302 | 0.205 |

短pilotでは傾きの誤差が大きくなります。GUIは近似σも併記します。原本VDIF SHAは4ファイル各1回。予定画像露光0.9秒。RMLは1初期値・100反復上限、Closure χ²/測定数0.9421で、画像品質の合格としていません。点源の処理経路確認です。

### 全回帰・独立CLI

- source216件成功、警告21472件、176.31秒。
- installed wheel216件成功、同警告、175.64秒。pip check成功。
- wheel 5,450,614bytes、SHA256 `5b9a9a86d35af7d475438a54d584f87fe4a3ff63b764dde413a37b25a0b8dc0b`。
- 実子プロセスの線形3区間解析と矛盾/未知モデルのAPI拒否を確認。
- checkout外のインストール済み `vsora-sequence --rate-model linear` で合成し、sourceのvisibility/weight/UVW/time/frequency/露光/power/SK/整数diagnosticsの全配列が一致。

警告は既存Baseband/NumPy・Starlette等です。警告ゼロではありません。

### 実Chromium

インストール済みGUIを独立temporary workspaceで動かしました。

- 初期値constant、linear選択でcheckboxの解除/無効化、constantへ戻して再有効化。
- 段階035の強い滑らかな変動の3秒VDIFから、線形補正→Closure→相対RMLまで実行。
- 新しい3区間fixtureから線形モデルを選び、傾き・近似σ・χ²・図・相対RMLを表示。
- 16時刻のpilotでは4部分の推定が揃わず、pilot後に日本語で停止。最終画像なし。
- Chromium153、日本語font成功、JS error0、外部request0、390pxの結果/入力に横はみ出しなし。

初回browser harnessはHTMLの0.1選択値を.1として指定し、操作で失敗しました。初回CLI harnessはclock_modelとclockの引数名を混同し、ソフト実行前に失敗しました。両方を修正して別の新規outputへ全経路を再実行しました。未完了の初回を成功として集計していません。

ブラウザRMLは1初期値・100反復のプロトコル確認で、反復上限です。Windowsブラウザ・WSLg・RTL-SDR実機は未検証。メインlocalhostサーバーは実行中ジョブ0を確認してから更新しました。

## 4. 再実行・保存記録

```bash
python tools/run.py workflows.linear_sequence_validation --output outputs/new-linear-sequence
python tools/verify_sequence_installed.py --manifest outputs/stage038-sequence/input/manifest.json --clock-model outputs/stage038-sequence/input/clock.json --reference outputs/stage038-sequence/sequence/synthesis/visibility.npz --rate-model linear --output outputs/new-installed-sequence
```

browser toolには単一区間・区間列それぞれのmanifest/clockと新規outputを指定します。大きなVDIFとログはGit外 `outputs/stage038-sequence/`、`outputs/stage038-browser-final/`、`outputs/stage038-installed-cli-final/`、`outputs/stage038-verification/`。公開の [区間モデル](../../validation/runs/stage038/sequence.json)、[CLI照合](../../validation/runs/stage038/installed-cli.json)、[browser結果](../../validation/runs/stage038/browser.json)、[全回帰/wheel](../../validation/runs/stage038/verification.json)、[解析画面](../../validation/runs/stage038/analysis.png)、[390px表示](../../validation/runs/stage038/mobile.png)を参照。

## 5. 制約・未解決事項

短区間・安定sky/gain・検出できるsignal・近似Gaussian Fisher covarianceに依存します。近似σ/χ²と計算coherenceの確率的校正は未実施。共通局rate、alias、各部分内の位相振動をこの選択で推定できません。観測条件は実機SEFDと位相安定性を測って決める必要があります。実観測のCas A画像完成を宣言する段階ではありません。

## 6. 次段階

滑らかな線形モデルで扱えない位相変動を物理IQ→VDIFで試し、減衰・Closure・検出/未判定の範囲を調べます。その後、低SNRと観測計画の評価へ進みます。
