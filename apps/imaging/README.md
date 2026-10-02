# 画像復元

較正済みの複素相関値からdirty画像を作り、点源応答を使うCLEANで天体成分を推定します。NPZとV-SoRAのFITS-IDIを読めます。未較正のADC²データをJy画像として扱わないよう、入力を検査します。

出力はdirty、PSF、model、restored、residualのFITSと比較図、停止条件を含むsummaryです。[結果の読み方](../../docs/guide/03-results.md)を参照してください。

現在は直接フーリエ計算による小規模CPU参照実装です。GPUや大規模観測の高速画像化は今後の作業です。
