# 段階125の正式記録

[レポート](../../../docs/reports/125-closure-residual-diagnostics.md)の保存済み18条件を記録する。

- [reference.json](reference.json)：3枝×元/共通基線×truth/prior/保存fit、損失・成分・基底のSHA・原本と派生物SHA。予測画像の再fitや再相関は実行していない。
- [cell-residuals.npz](cell-residuals.npz)：上記cases順18×8時刻×8channelの数・位相/振幅のエネルギー・局所損失・最大残差。valid=false、count=0は不足。NaNを0点として集計しない。
- [cell-residuals.png](cell-residuals.png)：共通基線のtruth/保存fitの局所損失。灰色は不足、色の下限1e-6は表示用で検定の閾値ではない。
- [verification.json](verification.json)：両45対象、全18CLI/11593配列/科学JSON/図画素、prefix、非上書き、原本SHA、package不変。全2206は収集のみ。全2116の引用元は121。

大容量の各時刻/channelの選択Closure行列・共分散・残差・whitened配列はGit管理外`outputs/stage125-source-study/`、同じ計算の導入済み照合は`outputs/stage125-installed-api/`に保存する。各`detail.npz`のSHAをreferenceに記録した。元入力は118/119とtruth113の公開SHAへ照合した。元028rawの当時のbyte不変を今回証明したとは扱わない。

`outputs/stage125-preparation/`に目的・固定条件・凍結SHA・対象試験・collect・進捗・初回ログを保存した。初回は派生コピーのmetadataを数値欄へ誤って含め、導入CLIがobject arrayを拒否した。科学coreや原本は変わらず、呼出側を修正して両対象・全18条件・全18CLIを再実行した。初回を正式件数へ加えていない。低SNR尤度・p値・coverage・実機性能の検証は行っていない。
