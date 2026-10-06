# V-SoRA

離れた複数のアンテナが記録した電波を組み合わせ、Cas A（超新星残骸）の画像を作るプロジェクトです。OCXOで基準周波数を安定させたRTL-SDRを使い、1.42GHz、最大基線長約600mの観測網を目指します。

現在は、Linux上でシミュレーター・相関器・較正・画像復元を段階的に開発しています。小規模の模擬IQから画像までの処理とCASAへの接続を検証しました。**実受信機での画像化は未検証**です。Windows収録ソフトはハードウェアの進捗に合わせて後で開発します。

## 初めて読む方へ

- [文書の入口](docs/README.md)：目的に応じた読み方と、現在の説明・過去の記録の区別
- [開発全体の時系列](docs/reports/overviews/development-history.md)：何を目的に、なぜこの順で開発したか
- [最終目標と要素別進捗](docs/reports/overviews/goal-and-progress.md)：必要な要素、その理由、確認済み範囲と残る完了条件
- [使い方と考え方](docs/guide/README.md)：理工系の学部生を想定した入門ガイド
- [最初の実行](docs/guide/02-first-run.md)：点源の模擬観測から画像を作る
- [結果の読み方](docs/guide/03-results.md)：画像・誤差・検証の適用範囲
- [実観測への準備](docs/guide/04-observation.md)：必要な入力と残る課題
- [用語集](docs/guide/glossary.md)

## 開発・再現のための文書

- [実行環境](docs/design/python-environment.md)、[現在の開発計画](docs/design/development-roadmap.md)
- [ソフト間の規約](interfaces/README.md)：時刻・単位・符号とファイル項目
- [段階レポート](docs/reports/README.md)：目的・作業・検証・失敗・制約
- [文献調査](docs/literature/README.md)、[記録の運用](AGENTS.md)

文書・コード・小さい検証結果をGitで管理します。実測局位置や大容量IQはローカルの観測データとして保存し、公開リポジトリへ個人情報を入れません。

## 構成

| フォルダ | 役割 |
| --- | --- |
| `apps/simulator/` | 天体モデルから相関値・模擬IQを作る |
| `apps/correlator/` | VDIFの読込み、時計補正、相関、較正 |
| `apps/imaging/` | CLEAN・Closure＋RMLによる画像復元、短露光の合成 |
| `apps/ui/` | 日本語ブラウザ画面、実行状態・画像・結果の保存 |
| `apps/recorder/` | Windows収録。現在は実装対象外 |
| `packages/observation/`, `packages/formats/` | 共通条件・幾何計算・ファイル入出力 |
| `interfaces/`, `configs/` | 入出力規約と公開の仮想観測設定 |
| `workflows/` | 一連の検証を再実行する入口 |
| `docs/`, `validation/` | 説明・設計・段階レポート・小さい結果 |
| `data/reference/` | 匿名化したCas A参照画像と出典 |

## 日本語GUI

[起動と操作](docs/guide/06-gui.md)を参照してください。WSL上で起動し、Windowsのブラウザから模擬観測・検証・実行履歴を操作します。

```sh
.user-venv/bin/pip install -r requirements/verified-ui-linux.txt
.user-venv/bin/pip install --no-deps -e .
.user-venv/bin/vsora-ui --workspace . --port 8765
```

短区間VDIF解析、Closure＋RML、有限区間列、短露光の合成、日本語の配置比較を実装しています。配置比較は同梱データだけでも実行できます。低SNRの実観測画像化と全夜の運用は未検証です。現在の検証範囲と次の開発は[現状整理](docs/guide/09-observation-readiness.md)で確認できます。

## 実観測の画像化方針

高精度な局の利得較正ができない前提で、数百ms〜数秒の相関とClosure＋RMLを主経路にします。局間の周波数差とsample整列は別に扱います。[Closureの設計](docs/design/closure-rml-plan.md)に条件・限界・開発順を記載します。

日本語GUIの「VDIF解析」で、観測条件と時計モデルを指定して短区間の相対画像を作れます。現在は600m・3秒以内の参照処理です。「合成画像」で別時刻の短露光をまとめられます。[入力規約](interfaces/closure-pipeline.md)を参照してください。
