# 段階017：周波数別雑音重みとRFI診断

- 作成日：2026-10-02
- 状態：完了（固定SK閾値の模擬診断）
- 比較元コミット：d6110c9

## この段階の読み方

局・周波数ごとのpowerの変動を調べ、模擬的な連続波とパルス妨害を除外しました。除外した値は消さず、重みをゼロにします。実機の誤検出率は未測定です。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・対象範囲

局ごとのchannel powerを残し、連続波・パルス状妨害に対応するchannelを除外する。周波数ごとに異なる雑音を相関の重みに反映する。

## 2. 完了条件

Gaussian雑音でSKの平均が1付近、利得に依存しない。模擬連続波/パルスを検出し、該当局を含むbaselineの重みを0にする。VDIF sessionにも接続、統計不足を明示。模擬点源の位置が維持され、visibility誤差8%未満。全回帰成功。

## 3. 実際に行った作業

- `quality.py`：瞬時FFT power PからS1=ΣP、S2=ΣP²、SK=(M+1)/(M−1)(M S2/S1²−1)。独立な複素Gaussianの期待値は1。[Nita & Garyの原論文](https://academic.oup.com/mnrasl/article/406/1/L60/1041152)を参照。
- 固定SK範囲[0.3,3]、最小128FFT、手動RF除外。閾値は試作上の仮定。Pearson分布に基づく指定false alarm制御は未実装。
- `fx.py`：2M/(channel P_i P_j)の重みを任意設定で選べる。flagsを基線へ伝播。値を削除せずゼロ重みで保持。
- session/aligned入口に任意spectral_quality設定。native shardにpower、SK、eligible、理由bit、有効数を保存。較正後も元単位の診断を残す。
- `workflows/spectral_quality_validation.py`と単体・統合試験を追加。

## 4. 検証条件・結果

```sh
.verification-venv/bin/python tools/run.py pytest -q
.verification-venv/bin/python tools/run.py workflows.spectral_quality_validation --output outputs/stage017-quality-validation-v2
```

- 全回帰 **80件成功**、既知Baseband warning873件。
- Gaussian20seed、各128FFT/64channel/4局、5120局channel判定で誤flag **0**、平均SK **1.00104**。これはこの有限試験の観測値で、false alarm確率0という主張ではない。
- 4局/1024FFTの模擬IQへ、同一channel連続波と1blockパルスを追加。8局channelをflag。相関の相対誤差は **9.9638→0.04769**（約996%→4.77%）。
- 点源真値1000Jy、仮定SEFD10000Jy。dirty peak **993.03 Jy/beam**、pixel `[34,29]`で真値位置と一致。
- 不足16FFTではeligible=false、SK判定なし。手動除外と無効入力は伝播。colored noiseで重みは解析値と8%以内。
- 最初のworkflowは画像APIへの引数順を誤り失敗。修正後、別出力へ再実行して上記判定を確認。最初の出力は合格扱いにしない。

[数値記録](../../validation/runs/stage017/summary.json)、[診断図](../../validation/runs/stage017/quality.png)。大きい生成入力はGit管理外。

## 5. 制約・未解決事項

実機RFIの検出率・誤検出率、Gaussianに近いRFI、量子化/lowpassで相関するFFT、非常に強い天体のself noiseは未確認。RFIをすべて検出できる機能ではない。1ms pilotではFFT数が不足しやすい。bandpass較正、実観測の確認、統計閾値の運用選択は後続。

## 6. 次段階

利用者向け文書を理工系学部生向けに書き直す。その後、Ubuntu/WSLからブラウザで操作できる日本語GUIを段階開発する。
