# 段階127の正式記録

[レポート](../../../docs/reports/127-matched-grid-image-control.md)の生成格子と復元格子を揃えた対照を記録する。

- [reference.json](reference.json)：flux集約・生成・SNR/分散/基底照合、3fit/9探索、27残差評価と同じ8格子oracleの追加9評価。32格子へ埋め込んだ正解のregularizerを、8格子のF比較に使わない。
- [comparison126.json](comparison126.json)：126の理想枝3fitは引用。新しい天空へ変わっており、同じ物理的天空の改善率・独立反復ではない。
- [images.npz](images.npz)：truth8（仮定flux総和）、embedded_truth（同じ点位置）、3fit（相対flux）。64秒角の中心格子。
- [cell-residuals.npz](cell-residuals.npz)：3case×3支持（training/unused/all）×4画像（fit/prior/embedded_truth/oracle8）×8時刻×8channel。valid=false/count0/NaNを0点にしない。
- [matched-grid.png](matched-grid.png)：同格子の学習/未使用損失、同じ8格子でのoracle/fit目的関数。p値・独立試行の統計ではない。
- [verification.json](verification.json)：両89対象/実CLI3/564配列/5生成archive・3学習archive byte/全JSON/3FITSとWCS/checksum/37moduleprefix/非上書き、package不変。全2239は収集のみ、最新全回帰121両2116を引用。

Git管理外`outputs/stage127-source-study/`に原本4SHA・量子化truth・生成データ・SNR/基底詳細・全3fitを保存し、`outputs/stage127-installed-api/`に導入版の独立再生成と実CLI3件・全照合を保存する。元入力は118の3相関とtruthを125の公開SHAへ照合した。`outputs/stage127-preparation/`には目的・固定条件・凍結SHA・対象試験・collect・初回ログを残す。

初回の独立点源和は、n方向余弦で逐次減算と括弧付きの二乗和の丸め差があり、24/1792点が初期の許容値を超えた。nの差は最大1.11e-16、該当visibility差最大約1.66e-10。fit前に停止し、定義した括弧付き式に参照計算を修正、off-axis/large-w試験を追加して両対象・全3fit/CLI3を再実行した。許容値やproduction数式を変更せず、初回を正式件数へ加えていない。これは高精度実機の検証ではない。
