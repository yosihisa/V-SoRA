# 段階151の正式記録

[レポート](../../../docs/reports/151-sequence-capacity-guard.md)、[reference.json](reference.json)、[measurements.json](measurements.json)、[verification.json](verification.json)を参照。

比較元150。既存RML容量式のprivate共用と系列の早期拒否、従来の計画/三次統計/非上書きの優先順、有効3窓系列の数値保持を検証した。新7試験、両43対象/全2328、wheel全byte/pipcheck、checkout外API/CLI、両実GUI各28worker/56downloadを新実行。

初回source全回帰1失敗/2325成功555.20秒は、全処理終了後に訂正し、初回成功を最終件数へ足していない。最初のBLAS未指定baselineも保持するが正式比較元にはせず、150の関数定義を独立プロセスへ読み込みBLAS1/OMP1で取得した比較元を使う。凍結sourceを途中で旧版へ戻していない。

新rawは主比較で作らず、032固定4局原本と131のmanifestを使う。各有効系列8 NPZ/120フィールド/34 JSON/画像NPYを比較し、JSONの実測elapsed_sだけを除く。既存回帰内の一時模擬データとは区別する。元script/log/初回失敗・wheel・実行環境はGit管理外outputs/stage151-preparationに保持する。

画素32/行列128MiBは容量条件であり、peakRSS/必要PC/36窓完走/実Cas A/低SNR尤度/全夜GPUを保証しない。seed/MCSEを伴う新しい科学MCではない。
