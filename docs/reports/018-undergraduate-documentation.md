# 段階018：学部生向け文書への整理

- 作成日：2026-10-02
- 状態：完了
- 比較元コミット：8362341

## 読者向け概要

処理を使うために、専門用語を最初から知っている必要がない文書へ整理しました。電圧・複素相関・画像の関係を説明し、短い模擬観測を試してから、結果の意味と実観測の準備を読める順番にしました。

## 1. 目的・対象範囲

利用者向け文書を理工系学部生が読み進められる水準へ書き直す。検証記録の数値と履歴を維持し、実測・仮定・計算・未実施を区別する。

## 2. 完了条件

入門ガイド、用語集、実行例、結果の読み方、実観測の準備を揃える。README・現行設計・ソフト別説明を更新。過去のレポートに平易な読み方を付ける。ローカルリンク切れがなく、最初の点源手順が実行できる。

## 3. 実際に行った作業

- `docs/guide/`に全体案内・原理・最初の実行・結果・実観測・用語集を新設。
- README、実行環境、開発計画、ソフト別READMEを現在の到達点へ書き直す。
- 容量/PC設計は仮定と計算式を先に示し、実装済みと将来案を分ける。従来の容量数値を維持。
- 段階000～017へ「この段階の読み方」を追加。数値・失敗・当時の実行条件を変更せず、用語集と評価の説明へ接続。
- 文献調査は導入前の記録であることを明示。仕様書に受け渡す情報の意味を補足。
- 次段階のレポートテンプレートにも読者向け概要を追加。`tools/check_docs.py`を追加し、ローカルMarkdownリンクを検査。

## 4. 検証条件・結果

```sh
.verification-venv/bin/python tools/check_docs.py
.verification-venv/bin/python tools/run.py vsora_simulator --config configs/experiments/ideal-point.json --output outputs/stage018-tutorial-point
.verification-venv/bin/python tools/run.py vsora_imaging --input outputs/stage018-tutorial-point/visibility.npz --output outputs/stage018-tutorial-image
```

リンク切れ0。現在のソースで標準点源の模擬観測・画像化が成功。詳細：[tutorial summary](../../validation/runs/stage018/tutorial-summary.json)。文書段階のため科学計算の全回帰は再実施しておらず、直前の段階017の80件成功と区別する。

数式の変数・単位、73秒角の概算と画像品質の違い、4時間spanと短い露光の違い、model較正の事前情報への依存、Jy/pixelとJy/beamの違いを本文で説明した。外部の学部生による読解評価は未実施。

## 5. 制約・未解決事項

仕様書と過去の詳細記録には、再現に必要な英語の項目名・コマンドを残した。GUIは次段階の予定として記載し、実装済みと扱わない。実測受信機の観測手順はまだ確定していない。

## 6. 次段階

WSL Ubuntu上のPython処理を、Windowsのブラウザから操作する日本語GUIを作る。模擬観測と主要検証から始め、入力一覧・較正・画像化へ拡張する。
