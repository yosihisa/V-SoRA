# 段階014：VDIFの時計・幾何sample整列

- 作成日：2026-10-02
- 状態：完了（既知線形時計、1秒以下・600m以下の参照chunk）
- 比較元コミット：ef6baa4

## この段階の読み方

供給された時計モデルを実際のVDIF読込みにつなぎました。sample位置の補間と天体方向の到着時間・RF位相を補正しました。時計を天体から自動推定する試験ではありません。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・対象範囲

時計mappingを収録ファイルの入口へ接続し、ADC開始ずれ・sample rate差・幾何delay・RF位相を補正する。弱い天体からの時計推定を自動化したとは扱わない。

## 2. 完了条件

連続波形を別々のADC時計で収録してVDIFへ量子化。補正後baseline相関が0.3%以内で一致。bufferを入力全長と独立に制限し、EOF出力を不完全と記録。実CLIと全回帰成功。

## 3. 実際に行った作業

- `aligned.py`, `correlate-aligned`：4096sample/frameを必要分だけ読み、時計mappingでfractional query。65tap Kaiser lowpassのgroup delayを補償してsinc補間。
- phase centerの幾何delayでquery時刻をずらし、RF位相も戻す。600m以下・1秒以下chunkではdelayを両端から線形補間。
- 有効bandは±0.3FS以内へ制限。channel weight=0でband外を保存し、多channel profileへ接続。
- 最初のbuffer検証で不要prefixを保持して12288sampleとなったため、読込み中のprefix破棄を追加。
- 供給されたclockモデルの局順・rate・範囲を検査。raw ADC単位を維持。

## 4. 検証条件・結果

```sh
python tools/run.py pytest -q
python tools/run.py vsora_correlator correlate-aligned --manifest manifest.json --clock-model clock.json --output outputs/aligned --integrations 8
```

4局、RF1.42 GHz、FS2.048 MHz、連続7tone、receiver noiseなし。開始offset[0,3.25,-2.4,0.3]sample、ADC rate誤差[0,+80,-65,0]ppmを独立生成。実VDIFへの8bit量子化と幾何RF位相を含める。

- 補正後baseline相関の相対spreadは完了条件0.3%以内。
- 最大buffer **8197sample/局**、1積分4096sample。最初の入力位置の分だけ巨大bufferを保持しない。
- 2ms×8積分、実span0.016秒、開始offset0.002秒。実CLIも同じ条件で成功。
- 入力末尾を越える要求は拒否、最終directoryなし、failure state=incomplete。
- 全回帰 **58件成功**、既知Baseband warning617件。

数値記録：[summary](../../validation/runs/stage014/summary.json)。入力・clock manifest・shardは`outputs/stage014-validation`、実CLI出力は`outputs/stage014-cli`。Git管理外。

## 5. 制約・未解決事項

- clockは供給した真値。GPS/校正で開始時刻と実sample rateを測る必要がある。VDIFの公称時刻だけから真値を確定できない。
- この検証は強いdeterministic signal。実観測Cas Aの低SNR、温度による非線形時計変化、RFI/LO差はここでは未確認。
- 1秒以下・600m以下の短chunk API。長時間全sessionの自動clock追従は未実装。
- lowpassによるband-dependent noiseを重みに完全反映していない。total power近似とfilterの残留bandpassを較正する必要がある。
- 主ビーム、偏波、絶対UTC、実測アンテナ位置の精度は未検証。

## 6. 次段階

pilot積分・flagging・入力検査を整え、実観測接続に必要な測定項目をまとめる。利用枠の消費量を確認しながら保存と最終確認を行う。
