# 段階129の正式記録

[レポート](../../../docs/reports/129-main-path-regularizer-transfer.md)の模擬電圧由来の保存相関への移送を記録する。

- [reference.json](reference.json)：固定3設定×3枝の新9fit/27探索、各自の係数での残差・罰則・画像差、fine32生成参照のデータ残差と125照合、初期reference/入力4/画像SHA。126の既定3fitは引用。
- [main-path-transfer.png](main-path-transfer.png)：同じ原本・全8時刻での形状差。新しい未使用予測や設定の推奨ではない。
- [images.npz](images.npz)：original reference_fine32、quantized_reference8、既定126の3引用画像、新9相対画像。quantized_reference8は生成天空でも厳密oracleでもない。
- [cell-residuals.npz](cell-residuals.npz)：9case×4画像（fit/prior/quantized_reference8/fine_reference32）×8時刻×8channelの全時刻評価。valid=false/count0/NaNを0点にしない。
- [verification.json](verification.json)：既存両93対象/導入実CLI9/54配列/初期reference9byte/9FITS数値WCSchecksum/37moduleprefix/非上書き、原本・package不変。全2243は収集のみ、最新全回帰121両2116を引用。

Git管理外`outputs/stage129-source-study/`に新9fit・詳細JSON・初期reference、`outputs/stage129-installed-api/`に導入実CLI9と照合を保存する。入力は126の3branch/all_training/training.npzと118truth.npy、公開126/125のSHAへ照合し再生成していない。`outputs/stage129-preparation/`に目的・固定条件・進捗・凍結SHA・対象試験・collectを保存した。

全8時刻を使ったfitなので未使用集合は空。今回新しいholdout予測性能を測っていない。fine32参照の罰則は8格子fitのF比較に使わず、データ残差だけを別保存した。初期referenceは不変のconstructor/prior/seedの式から計算したものでoptimizer traceではない。新API/solverを変更せず、既存93試験と実CLI・目的関数の照合を行い、実CLIと目的関数の照合を主検証とした。
