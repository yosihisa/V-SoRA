# 段階142：有限周期bandlimitの既知雑音参照

[レポート](../../../docs/reports/142-periodic-fft-noise-reference.md)、[概要](reference.json)、[79数値配列](arrays.npz)、[正式検証](verification.json)、[資源](measurements.json)を保存する。NPZは数値だけでobject/pathなし。

sourceは `python tools/run.py workflows.periodic_fft_noise_validation --output <new-output>`。nativeはcheckout外から `python <checkout>/workflows/periodic_fft_noise_validation.py --output <new-output>`、runner/PYTHONPATHなし、OMP/OpenBLAS各1で実行した。wrapper自体はcheckoutが必要。

P512のみ4096 MC/seed142/batch32、3channelは同一電圧を共有する。131公称period6225920と無限周期は同じ小operatorの計算値で、131電圧の再処理・画像尤度の校正ではない。geometry/LO/ADC/flag/未知局応答を含まない。原本はreadonly SHA保持、新full/wheel/GUIは138を引用した。
