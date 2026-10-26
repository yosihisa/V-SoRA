# 段階126の正式記録

[レポート](../../../docs/reports/126-temporal-image-validation.md)の条件付き時刻分割を記録する。

- [reference.json](reference.json)：3枝×偶数/奇数/全時刻の9fit、27探索の終了状態、学習/未使用/全時刻に対するfit/prior/truthの計81評価、画像差、全設定、原本・派生archive・画像SHA。
- [training-unused.png](training-unused.png)：固定格子の学習・未使用時刻のデータ損失。破線は全時刻を使ったfitの学習損失で、未使用予測ではない。p値や独立試行の統計ではない。
- [images.npz](images.npz)：9つの8×8相対flux画像。キーはbranch__split、画像原点・64秒角の中心格子は119と同じ。実機画像ではない。
- [cell-residuals.npz](cell-residuals.npz)：9case×3支持（training/unused/all）×3画像（fit/prior/truth）×8時刻×8channelの数値。referenceのcell_array_rowが第1軸。valid=false/count0/NaNを0点にしない。
- [verification.json](verification.json)：両74対象/9実CLI/109配列/9FITS・WCS・checksum/全科学JSON/図画素、37moduleの読込先・非上書き・package不変。全2224はcollectのみ、最新全回帰121両2116を引用。

Git管理外`outputs/stage126-source-study/`に最小学習入力・全9fit・詳細セルJSON、`outputs/stage126-installed-api/`に独立CLI9件と照合を保存する。原本は118の3相関とtruth、125で登録した公開SHAへ照合した。`outputs/stage126-preparation/`に正式目的・固定条件・進捗・対象試験・collect・凍結SHA・初回ログを残す。

初回は存在しない既存試験名を指定して収集前に停止、次の初回sourceは6fit後にJy読込のvis_jy別名を誤って追加配列と扱った照合で停止した。別名を除いたwhitelist照合と単位別2試験へ修正し、最終74対象と9fit/9CLIを全て再実行した。最初の6画像は最終画像とbyte一致したが、正式件数へ加えていない。全処理終了後に変更・凍結を行い、正式検証中のソース変更はしていない。

分割は同じ保存観測の中で行い、LO/weight/共通maskの推定情報を共有しうる。独立した電圧生成・雑音試行・実観測の検証と扱わない。真値と未使用値をfitの選択に使わず、truthの読込も全9fit終了後に行った。
