# 段階149の小容量記録

[レポート](../../../docs/reports/149-finite-capacity-limits.md)と[人向け案内](../../../docs/guide/finite-capacity-and-limits.md)を参照。

- [capacity.json](capacity.json)：固定VDIFの4時間長について既存整数関数と独立payload/header式を比較。32 VDIFのstat/SHA、4通りの行列byte計算。取得速度・全夜性能は未測定。
- [api-probes.json](api-probes.json)：両環境で36/37/64窓の純計画3呼出と37窓RMLの128MiB超過拒否1呼出。全JSON/24輸入module bytes一致、位置確認。実相関値/Closure/Fourier行列/画像fitや全系列の完走は対象外。
- [source-audit.json](source-audit.json)：6file/10関数・メソッドの行範囲とSHA、既存試験・引用15fileのSHA。試験はreviewのみ。
- [verification.json](verification.json)：実施/未実施、451凍結項目・対象外tracked1462・原本76SHAの保持、公開監査とリンク、予算。138の全回帰/wheel/GUI、139有限運用、147対象回帰は引用。

再現する整数式は`frames=秒数×2048000÷4096`（ここでは整数）、`VDIF bytes=frames×8×(4096×2+32)`。独立側は`秒数×2048000×8×2+frames×8×32`。既存`workflows/independent_raw_matrix.py:expected_vdif_bytes`本体だけをASTで取り出して4回実行し、generator import/entrypointは実行していない。

計画はFs2048000、FFT8、blocks1024、8局、pilot750、画像0.3秒、start0.002秒、step=None。行列式は`窓数×8×28×pixels²×16`で、上限`128×1024²`と比較する。37窓shape(37,8,28)の有限ゼロuvw/visibilityと重み1・全pairを既存constructorへ渡し、行列guardのValueErrorだけを確認した。sourceは明示src wrapper、installedはcheckout外cwd・runner/PYTHONPATHなし。詳細script/log・絶対pathはGit管理外`outputs/stage149-preparation/`に保持する。

seed/MCSE対象外、科学MC0、新pytest/全回帰/wheel/browser0。新生成raw/取得/相関/画像なし。容量計算から実運用の速度、必要PC、低SNRの妥当性を認定しない。
