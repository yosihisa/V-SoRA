# 段階123の正式記録

[レポート](../../../docs/reports/123-paired-w0-rml-reference.md)に対応する。

- [verification.json](verification.json)：58対象/collect/引用全回帰、prefix/非上書き/byte照合。
- [metadata.json](metadata.json)：1条件の生成と事前固定設定、原本SHA、人工weight、継承した3秒積分情報。
- [native.json](native.json)、[external.json](external.json)：全3初期値と実optimizer終了状態。非収束を除外しない。
- [assessment.json](assessment.json)：共通の全支持領域110秒角/平行移動NRMSEとnative公開損失。
- [images.npz](images.npz)、[image-comparison.png](image-comparison.png)：正解・prior・native・外部の相対画像と表示。実観測画像ではない。
- [regression122.json](regression122.json)：接続classのfactory抽出後の、旧外部DFT60/Closure6/w27の回帰。

Git管理外の`outputs/stage123-source-reference/`に入力bundleと別置きtruth/gain、`outputs/stage123-source-native/`にsourceのfit、`outputs/stage123-installed-api/`にcheckout外のnative/外部2実行/後評価、`outputs/stage123-preparation/`に目的・進捗・試験・ログを保存した。初回・途中の確認は正式成功へ合算していない。元の118/119入力はリポジトリ外に管理され、この生成の再現には記録したSHAと同じ原本が必要。画像だけから原本を再生成したことにはならない。
