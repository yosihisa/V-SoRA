# 段階013：多channel FITS-IDIと全視野CLEANの修正

- 作成日：2026-10-02
- 状態：完了（単一XX・等間隔channel）
- 比較元コミット：c0c27dd

## この段階の読み方

周波数ごとの相関値・重みを外部ソフトへ保存しました。また、視野の端でCLEANが発散する問題を、各点の正確な画像応答を計算する方式で修正しました。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・対象範囲

時間・周波数情報とchannel別flags/weightsを外部ソフトへ渡す。偏心点源を全視野で画像化し、相関・形式・復元の独立性を確認する。

## 2. 完了条件

多channelの内部読み戻し・FITS軸・checksumを検証。CASAで8channelの周波数・flags・visibility・点源位置/振幅が一致。自作CLEANも偏心点源を全視野で収束させる。全回帰と既存ADC CLI成功。

## 3. 実際に行った作業

- FITS-IDI v3：time/channel/baseline visibility、channel別逆分散。UVWは光秒、各channelのRFへ換算。
- `apply`はspectral-visibility.fitsも保存。重みがchannelで異なる場合はcontinuum近似を行わない。
- 画像CLIで較正済みnative spectral/多channel IDIを読込み、狭帯域MFS。raw ADCを拒否。
- CASA検証でWEIGHT/SIGMAとWEIGHT_SPECTRUM/SIGMA_SPECTRUMを復元し、周波数・zero-weight flagsを確認。
- **偏心点源の全視野CLEANで発散を検出**。中央PSFの切出しを平行移動する近似では、画像端の応答が欠け、w項の位置依存も失う。CLIを各点の正確なuvw normal operatorで引算する方式へ修正。応答cacheは約16MiB上限。

## 4. 検証条件・結果

```sh
python tools/run.py pytest -q
python tools/run.py workflows.export_casa_fixture --output outputs/spectral-fixture --channels 8
python3 tools/run_casa.py tools/verify_casa.py --input outputs/spectral-fixture/point.fits --expected outputs/spectral-fixture/expected.npz --output outputs/casa-spectral --image
python tools/run.py vsora_imaging --input outputs/spectral-fixture/point.fits --output outputs/native-image
```

4局、10時刻、8channel、channel間隔256 kHz、異なる逆分散、1channel測定をweight=0。西48秒角・北32秒角1000 Jy点源。

- CASA：60 MS行×8channel、visibility相対誤差2.29e-8、uvw誤差9.94e-17、周波数差0 Hz、時刻差0秒（保存double基準）、flags1個がzero weightsと一致。
- 復元したchannel重み誤差2.08e-8。CASA期待pixel[67,66]に観測[67,66]、peak1000.000793 Jy/beam。
- 自作修正前：5000回で非収束、peak約2.77e38へ発散。合格扱いにしていない。
- 自作修正後：**66回で収束**、model999.044994 Jy、restored peak999.999999 Jy/beam。独立点源式でdirty=1000×exact responseが1e-10以内で一致。
- 全回帰 **57件成功**、既知Baseband warning553件。ADC CLI再検証は平均visibility誤差0.8849%、peak1000.000003 Jy/beam、収束。

詳細：[CASA summary](../../validation/runs/stage013/casa-summary.json)、[自作画像summary](../../validation/runs/stage013/native-summary.json)、[画像](../../validation/runs/stage013/native-images.png)、[8channel入力](../../validation/runs/stage013/point-8channel.fits)。大容量出力は`outputs/stage013-*`、Git管理外。

## 5. 制約・未解決事項

- 単一XX/source/band、正方向・等間隔channelのみ。AIPS・多偏波・多bandは未検証。
- native MFSは帯域内でflux一定を仮定。広帯域spectral index推定は未実装。
- 正確な点応答は小規模CPU参照処理で、巨大visibilityの高速gridding/GPU backendは未実装。
- 既存`clean()`のcallbackなしAPIは旧近似を残す。CLIはexact方式を使う。旧レポート・図は当時の近似結果を保存している。
- 主ビーム/RFI/bandpass、実測UTC同期・実観測fluxは未確認。

## 6. 次段階

時計mappingと幾何sample整列を収録ファイルの処理入口に接続する。利用枠内で検証と記録を完了できる範囲に区切る。
