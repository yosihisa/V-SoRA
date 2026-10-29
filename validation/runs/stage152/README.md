# 段階152：実整列APIの有限平均参照

[レポート](../../../docs/reports/152-aligned-forward-mean.md)、[reference.json](reference.json)、[verification.json](verification.json)を参照。比較元151。

新workflowは既存146の独立FIR tapを再利用し、実correlate_alignedのJSON/clock/profile/幾何/SampleBuffer/位相/FX/保存を、独立な任意queryのsinc・DFT・位相係数へ接続する。readerだけ合成decoded64sample frameへ差替え、実codec/header/量子化/未知推定/選別/画像は処理しない。

3局/raw512/FFT8×16block・62.5µs、3mode±の6probe×2供給rate条件。各12API、両42既存対象、summary/19配列/12NPZの180フィールドがsource/installedで完全一致。Gaussian/proper/IIDの標本ではなく、有限second moment A A*/3の決定論的参照。seed/MCSE対象外。負対照は参照計算だけ。

実行はsourceで `python tools/run.py workflows.aligned_mean_validation --raw-reference outputs/stage131-source-study --output outputs/stage152-source-study`。nativeはcheckout外/PYTHONPATHなしで同じworkflow scriptを呼び、製品21moduleの正確prefixを確認する。helper/期待記録はcheckoutを要する。出力再使用は拒否する。

原本131は所在確認に使う3ファイルも含め76SHA保持し、payloadを主比較へ渡していない。通常APIが生成するvdif_validation_scope等のラベルを、この差替え試験のheader証拠としない。大係数配列/私的な絶対path/logはoutputsに保持。全回帰/wheel/GUIは151の引用で、152では新実行していない。
