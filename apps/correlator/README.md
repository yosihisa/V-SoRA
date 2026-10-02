# 相関器と較正

各局のVDIFを読み、同じ電波の共通成分を時間・周波数・基線ごとに取り出します。較正前の単位はADC²です。天体モデル等を使って局の応答を推定し、Jyへ較正してから画像ソフトへ渡します。

- `correlate`：時刻が揃ったframeを相関。幾何補正は積分中央の位相補正。
- `correlate-aligned`：実clockモデルを入力し、sample位置とRF位相を合わせて短区間を相関。
- `calibrate` / `apply`：既知点源または天体形状モデルから応答を推定 / 相関値へ適用。
- `casa-input`：FITS自身の重みをCASAへ持ち込むbridgeを作成。

[session規約](../../interfaces/session-manifest.md)、[clock規約](../../interfaces/clock-model.md)、[実観測の準備](../../docs/guide/04-observation.md)を参照してください。
