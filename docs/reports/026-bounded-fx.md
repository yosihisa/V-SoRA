# 段階026：統計を保持した相関の分割処理

- 作成日：2026-10-02
- 状態：分割処理・有限比較・配布版更新完了
- 比較元コミット：c7d6dcd

## 読者向け概要

相関は、短いFFTごとの積を足して、使えたFFTの個数で割ります。積分全体の電圧を一度にメモリへ置く必要はありません。電圧を小分けに読み、相関と雑音の統計だけを残すよう変更しました。各小分けで電波妨害を判定すると結果が変わるため、品質の統計も全体へ足してから判定しています。

## 1. 目的・対象範囲

整列再相関のメモリを制限し、相関値・重み・有効露光・channel power/SK/flagを保持。段階025の感度計画も含むwheel再配布。3秒pilot、長記録の連続session、GPU、高速化はこの段階の対象外。

## 2. 完了条件

- FFTブロック単位でcross-products、power、第四次moment、有効数を集計する。
- 一括FXと欠損・tone・gain・channel重み有無で一致。
- 同じ8局1秒VDIFを前段階と比較し、SHA・最大差・buffer・RSS・時間を残す。
- source/wheel全試験とcheckout外CLI/GUIを確認。

## 3. 実際に行った作業

- `stream_fx.py`：FXAccumulator。unitary FFT、joint baseline有効数、station/sample power、power²、最後のSK・flagと重み、単一短積分の結果。
- `aligned.py`：各積分を8192sample以内へ分割。幾何とrate補正はsampleごとに同じ計算。summaryに最大chunkと集計方法。
- `test_stream_fx.py`：ランダム波、gain、CW、局別欠損、qualityなし/total/channel重み、ゼロ有効露光、finish後の更新拒否。
- `workflows/stream_fx_validation.py`：前段階の固定コミット実装も別プロセスで呼び、同じ原本・rate・既存相関SHAで比較。
- `tools/verify_closure_installed.py`：配布版の感度GUIを追加確認。[規約](../../interfaces/closure-pipeline.md)を更新。

## 4. 検証条件・結果

Python3.12.3/NumPy2.5.1/SciPy1.18.0/Astropy7.2.2/Baseband4.3.0。段階024のshot00、8局Cas Aの1.04秒VDIFから、1秒・Fs2.048MHz・FFT8を再相関。既に推定したrate profileを両実装へ同じ条件で入力。OpenBLAS/OMP各1thread。各ベンチは別Pythonプロセス、WSLで一回ずつ。開発中の他の負荷を完全には固定していないため、速度は概算値。

| 項目 | 前段階 | 分割処理 |
| --- | --- | --- |
| 最大局buffer | 2,052,100sample | 12,292sample |
| FX一chunk | 2,048,000sample | 8,192sample |
| プロセスpeak RSS | 1,488,176KiB（約1.42GiB） | 333,036KiB（約325MiB） |
| 経過時間 | 23.39秒 | 18.66秒 |
| 保存相関の最大正規化差 | 基準と0 | 2.18e-14以内 |
| 重み・channel power | 基準と0 | 2.50e-14以内 |
| SK | 基準と0 | 1.28e-13以内 |
| flag・valid数・UVW・時刻・露光 | 基準と同一 | 同一 |

正規化差は各配列の最大差/max(基準の最大絶対値,1)。SKは入力のpower平均とpower²和を別の順番で足すため小さい丸め差があります。flag/countは整数・boolで完全一致。時間から見て、このCPU参照処理は8局全量の実時間処理ではありません。

source129件、wheel再導入129件成功。3034既知deprecation warning、pip check成功。checkout外wheelのVDIF解析CLI/GUI、感度GUI完了。ADC²、相対総量1、実測でない期待Closure情報0の表示を確認。新CLI含む6入口help成功。ブラウザのstaticは段階025と同じで、その時点のChromium検証を維持。この段階のcheckout外GUIはAPI実行で確認。

```bash
python tools/run.py pytest -q
python -m pytest -q
python tools/run.py workflows.stream_fx_validation --manifest outputs/stage024-vdif-casa-sefd1000/shot-00/input/manifest.json --clock-model outputs/stage024-vdif-casa-sefd1000/shot-00/input/clock.json --rate-profile outputs/stage024-vdif-casa-sefd1000/shot-00/pipeline/rate-only.json --reference outputs/stage024-vdif-casa-sefd1000/shot-00/pipeline/correlation/shard-00000.npz --output outputs/stage026-stream
# 前段階比較は上記に --legacy-stage025 を加え、別outputを指定する
python tools/verify_closure_installed.py --manifest outputs/stage023-vdif-closure/input/manifest.json --clock-model outputs/stage023-vdif-closure/input/clock.json --output outputs/stage026-installed-check
```

[分割記録](../../validation/runs/stage026/stream-summary.json)、[前段階記録](../../validation/runs/stage026/legacy-summary.json)、[checkout外確認](../../validation/runs/stage026/installed-summary.json)、[検証とwheel SHA](../../validation/runs/stage026/verification.json)。wheel5,428,439byte。原本と内部分割manifestはGit外outputs/stage026-*、個人を含むローカルパスは公開記録へ含めない。

## 5. 制約・未解決事項

積分全体のspectral統計は従来と同じですが、弱い天体と独立baselineの雑音近似自体は変わりません。sample補間はCPU参照実装で速度が不足しています。長時間原本のhash/readの費用、全sessionのshard/進捗、GPUは未検証。pipelineの整列/rateは1秒以内の制限を維持しています。

## 6. 次段階

sample幾何を1秒以下の区間で補間しながら、数秒のpilot/画像積分を扱う。一定rate・安定gainがその期間に成立する模擬条件で検証し、実OCXOの位相安定時間とは区別する。
