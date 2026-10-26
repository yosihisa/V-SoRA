# 段階124の正式記録

[レポート](../../../docs/reports/124-ehtim-iteration-gradient-controls.md)の実行と数値を残す。

- [verification.json](verification.json)：71対象/引用全回帰、主勾配4/12適合・8/12不適合、secondaryとの区別、prefix・原本・package照合。
- [iterations.json](iterations.json)：2上限×3初期値、各初期/終了点、全5方向×3stepと実optimizer状態。
- [comparison.json](comparison.json)：800の引用と2000/5000の目的関数・共通NRMSE・共通データ損失。
- [images.npz](images.npz)、[iteration-controls.png](iteration-controls.png)：同じ人工参照の相対画像と診断図。実観測の性能ではない。
- [regression123.json](regression123.json)、[regression122.json](regression122.json)：既定800と形式接続の回帰。

`outputs/stage124-installed-api/`にcheckout外の両実行・後評価・非上書き、`outputs/stage124-preparation/`に正式目的/進捗/対象試験/予備ログ、`outputs/stage124-regression123/`と`outputs/stage124-regression122/`に旧経路を保存した。入力は123の原本bundleを変更せず再利用した。予備・再実行を独立条件へ合算しない。主判定の不適合を、実装試験71成功やsecondary小差によって合格へ置換していない。
