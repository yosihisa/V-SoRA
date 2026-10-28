# 段階141：既知色付きFIRの有限参照

[レポート](../../../docs/reports/141-colored-fft-noise-reference.md)、[科学概要](reference.json)、[42数値配列](arrays.npz)、[検証](verification.json)、[資源](measurements.json)を保存する。NPZは数値配列だけで、local pathやobjectは含まない。

sourceは `python tools/run.py workflows.colored_fft_noise_validation --output <new-output>`。導入版はcheckout外から `python <checkout>/workflows/colored_fft_noise_validation.py --output <new-output>` を実行し、PYTHONPATHやrunnerを渡さない。固定4096/color・seed141・batch32・3共有channel。OMP/OPENBLAS各1で正式比較した。wrapper自身はcheckoutが必要。

母共分散・合成operatorは既知。二つのcolorと三つのchannelは生電圧を共有し、source/nativeの同seed再実行も独立な追加試行として数えない。誤差モデルの検証であり、実効FFT数・実機confidence・画像尤度の校正ではない。全回帰/wheel/GUIは138を引用、新しく実行していない。初回shape失敗ログ/未完成出力・module絶対pathはGit管理外に保持。
