# 段階135の保存相関・条件付き全雑音診断

- [科学記録](reference.json)：全96セルのscalar/入力識別、比較基底・分散比/相関差、保存配列のdtype/shape/SHA。36条件付き/60inactive/6空制約を保持。
- [検証](verification.json)：両91対象、全2277はcollectのみ、96JSON byteと594数値/boolean欄、原本/相関/真値SHA、prefix・非上書き・旧package不変。
- [計測と条件別集計](measurements.json)：各source API/native CLIの有限時間・出力サイズ。画像/GPU/全夜のbenchmarkではない。
- [固定例の図](comparison.png)：同じ行・列の条件付き相関係数。実測誤差や画像改善ではない。

大きな診断JSON・配列はGit外outputs/stage135-source-study/とoutputs/stage135-installed-api/study/。元相関はoutputs/stage132-source-study/、公開133/referenceの12SHAへ照合した。真値画像は数値を参照せず、識別SHAだけ確認。

sourceはtools/run.py workflows.saved_noise_contract_validation --reference 相関study --record133 公開133/reference.json --output 新出力。導入側はcheckout外からtools/verify_saved_noise_contract_installed.pyを絶対指定し、96回の既存noise_diagnostics CLIを実行。helperはcheckoutにある。既存出力を再使用しない。

047既定SNR5と比較のSNR10を分け、共通有効行とproduction QR基底で比較する。無効/空/振幅なしのmetricsを0へ置換しない。名目FFT数をIIDとして置いた条件付き計算で、実独立性・coverage・低SNR尤度・実Cas Aを検証していない。production RMLのweight/採否/画像は変更しない。
