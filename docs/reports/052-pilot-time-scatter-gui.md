# 段階052：pilot時間散乱の日本語GUI

- 作成日：2026-10-04
- 状態：完了（保存pilot診断のGUIの範囲）
- 比較元コミット：aa1c535

## 読者向け概要

保存pilotを選び、同じRFで時間方向にどれだけ相関が散らばるかを日本語画面で確認します。診断処理の完了と、条件付き推定・信号power不足を分けて表示します。相関を時間ごとに二乗して平均したpowerと、平均してから二乗したpowerの差を読みます。

## 1. 目的・対象範囲

既存の雑音診断画面へ段階051の時間散乱診断を追加。任意のrate profile、保存軸・pilot履歴・基線別powerと無制限の比、未判定と日本語エラーを扱います。

## 2. 完了条件

厳格な要求検証、実workerのAPI一致・JSON保存、旧情報不足・信号power不足・二重補正とprofile不一致を確認。最終wheelの実Chromiumで保存pilot・対照・旧/弱fixture、種類切替・RF・JSON・日本語/390px/外部通信/JSを確認し、既存一cell GUIも回帰すること。source/wheel全回帰、匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`、`jobs.py`：整数channelと任意profileの`time_scatter`要求、日本語履歴名。個別時刻・余分なコマンドは受け付けない。
- `worker.py`：別processで段階051APIを実行し、JSONを保存。範囲外・二重補正・局/UTC不一致・profile有効期間外を日本語表示。
- `static/index.html`、`static/app.js`：診断種類・任意profile・RF選択・全時刻の説明。履歴へ保存pilotを追加。一cellへ戻すと時刻を再選択できる。基線別の時間/平均power・差・無制限の比、未判定を表示。
- `apps/ui/tests/test_time_scatter_gui.py`、`tools/verify_time_scatter_ui.py`：実workerと配布版の実ブラウザ検証。
- [操作ガイド](../guide/06-gui.md)、[入力規約](../../interfaces/pilot-time-scatter.md)、索引、小容量の実行記録。

## 4. 検証条件・結果

### 要求と実worker

最終対象24件成功、警告1件、4.05秒。新しい14件と既存一cell GUI10件を含みます。64時刻×3channel×4局の構成統計で、軸読込・profileを含めたAPI一致・SHA256・JSON保存を確認。旧FFT数不足は未判定、相関を0にしたfixtureは処理完了でも全基線のpower不足でした。

不正整数/bool・空profile・余分な個別時刻/コマンドを拒否。profileなしファイル・二重補正・UTC不一致・有効期間外はジョブ失敗として日本語理由を残しました。これらはGUI転送用の構成統計で、全状態の実電圧を新たに生成した意味ではありません。

### 最終wheelの実ブラウザ

Python3.12.3・Playwright1.63.0・Chromium153.0.8010.12、WSL headless。checkout外の独立workspaceで最終wheel GUI/worker/診断APIを実行しました。段階051の固定模擬VDIF由来pilotをコピーし、保存profileと中央RF1420MHzを選びました。この段階でVDIFを新しく再相関したという意味ではありません。

| 画面で選んだ入力 | 処理 | 診断 | 表示 |
| --- | --- | --- | --- |
| 高速位相pilot・保存線形profile | 完了 | 条件付き | 最小power比約0.726195 |
| 対照pilot・保存一定profile | 完了 | 条件付き | 最小power比約0.985247、1超も保持 |
| 共通基線FFT数を除いたfixture | 完了 | 未判定 | 不適格な時間cellの説明 |
| 相関値を0にしたfixture | 完了 | 条件付き・全基線未判定 | 信号power不足、比は— |
| 補正済みmarkerを加えたfixtureに追加profile | 失敗 | 未生成 | 二重補正の日本語理由 |

後3例は保存統計を変更したfixtureです。履歴選択も独立workspaceに作った固定履歴fixtureで、新しい解析の実行ではありません。初回は検証用履歴の作成時刻が実ジョブより未来となり、ツールが最新一覧から誤ったfixtureを読んで停止しました。fixture時刻と、ジョブ作成APIの返したIDで確認するよう検証ツールを修正し、再実行成功しました。製品の履歴順は変更していません。表の6基線の値とinstalled API、入力/profile SHA256、JSONダウンロードが一致。種類を切り替えた時刻/profile欄の有効状態を確認。

JSエラー0・外部通信0・同梱日本語フォント成功。390pxの入力・信号不足結果で横はみ出しなし。画面を目視でも確認しました。Windows/WSLgの実ブラウザは未検証です。

段階048の既存一cellブラウザ検証も同じ最終wheelで実行し、4状態・RF/時刻・JSON・低SNR無効行・日本語/390px/JS/外部通信を再確認しました。常用localhost:8765は実行中ジョブがないことを確認して最終wheelへ再起動し、39件の履歴を保持しました。

### 全回帰・配布

source447件成功、警告23952件、423.57秒。installed447件成功、警告23952件、423.02秒。source→2種類の実ブラウザ→installed全回帰を順番に実施、試験除外なし。既存Baseband/NumPy・Starlette等のdeprecation警告を含みます。pip check成功。

wheel5477226bytes、SHA256 `1f2eb06a5b68fc966151d5c305bd9b1de438d9498d3ce79370b473e9195ee10a`。

[時間散乱ブラウザ記録](../../validation/runs/stage052/browser.json)、[診断画面](../../validation/runs/stage052/result.png)、[390px入力](../../validation/runs/stage052/mobile-input.png)、[390px信号不足](../../validation/runs/stage052/mobile-result.png)、[既存一cellブラウザ回帰](../../validation/runs/stage052/existing-noise-browser.json)、[回帰・wheel](../../validation/runs/stage052/verification.json)。完全ログ・wheelはGit外`outputs/stage052-*/`です。

```bash
python tools/verify_time_scatter_ui.py --archive outputs/stage051-replay-final --source-profiles outputs/stage039-periodic --output outputs/new-time-scatter-ui
```

最終wheelを導入したPython、閉じた段階051/039archive、Playwright・Chromiumが必要です。

## 5. 制約・未解決事項

実FFT/time cellの独立性・同じpilotで推定したprofileの依存性・実機信頼区間・Cas A画像品質は未確認。ratioはpower比で、振幅保持率や実機coherenceではありません。phaseだけの変動と断定せず、負や1超も保持します。RML重み・自動停止基準は変更していません。

## 6. 次段階

低SNRのClosure統計を検討・検証します。独立電圧標本を使う三次統計で雑音の偏りを除けるか調べ、実機や画像化への導入判断は後の段階とします。
