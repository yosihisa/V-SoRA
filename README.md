# V-SoRA

VLBI の相関器、画像復元処理、およびそれらを動作確認するためのシミュレーターを開発するリポジトリです。文献調査と動作確認の記録もここで管理します。

観測目標は、OCXO改造RTL-SDRによる最大基線長約600 mの観測網で、1.42 GHzのCas Aを画像化することです。Linux処理系を段階的に開発しています。現在の到達点は開発レポートを参照してください。

- [初期レポート・開発構想](docs/reports/000-initial-plan.md)
- [開発段階レポート一覧](docs/reports/README.md)
- [開発と記録の運用](AGENTS.md)

開発段階ごとに目的・実作業・検証結果をレポートにまとめ、その段階の変更と一緒にGitコミットします。以下は現在のソフト別構成です。

## フォルダ構成

| パス | 用途 |
| --- | --- |
| `apps/simulator/` | 天体・visibility・IQの生成 |
| `apps/correlator/` | 相関・visibility出力 |
| `apps/imaging/` | 校正と画像復元 |
| `apps/recorder/` | Windows収録（現在対象外） |
| `packages/observation/` | 共通観測条件・幾何 |
| `packages/formats/` | ソフト間データの入出力 |
| `interfaces/` | 単位・時刻・符号と受け渡し規約 |
| `configs/` | 局配置・天体・実験条件 |
| `workflows/` | 一連の処理を再実行する入口 |
| `docs/reports/` | 段階ごとの目的・作業・検証結果 |
| `docs/design/`, `docs/literature/` | 設計・文献 |
| `validation/` | 検証計画・実行結果・小容量の図 |
| `data/reference/` | 匿名化した参照画像と出典 |

## 実行

[環境と再実行方法](docs/design/python-environment.md)、[Linux開発計画](docs/design/development-roadmap.md)、[ソフト間規約](interfaces/README.md)を参照。

```sh
python tools/run.py pytest -q
```

大容量の収録・生成データはGit管理外に置き、所在と再現条件を記録する。
