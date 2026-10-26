# 段階131の独立seed原本記録

[レポート](../../../docs/reports/131-independent-raw-matrix.md)は、4つの固定条件の原本生成と構造・再現までを記録する。相関・未知LO推定・画像化は未実施。

- [reference.json](reference.json)：固定行列、仮定・生成seed、全76原本file SHA、truth/generation/境界SHA、全header検査と先頭/末尾復号の数値SHA。
- [measurements.json](measurements.json)：各所有workerの生成/構造検査の壁時計秒とpeak RSS、実保存容量。最低PCや全夜/GPUのbenchmarkではない。
- [verification.json](verification.json)：両14対象、両48640header/64境界、全原本byte/68配列/全JSON、34moduleprefix、非上書き、引用全回帰とcollectの区別。

大容量の原本は`outputs/stage131-source-study/`、導入coreの同じ4条件は`outputs/stage131-installed-api/study/`。`input/`の外へtruth.npy/generation.jsonを分け、観測modelはunknown・fluxなし。config.seed42は生成seedではない。観測noise.enabledはrawのSEFD雑音を表すTrueへ修正した。全原本は同じepoch、SEFD仮定ごと2seedだがgain/LO/noiseが一緒に変わり、noise-only介入や零天空false-alarm試験ではない。

`outputs/stage131-preparation/`に目的・資源/サイズ調査・凍結SHA・対象試験/collect・進捗・初回immutable-header試験失敗を保持。source/導入のhelperはcheckoutを必要とし、導入側は数値packageを導入prefixから読む。helperまでwheelのみで動くと主張しない。ローカルpathを含むruntime-private.json/logは公開しない。
