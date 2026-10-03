# 段階034：固定原本の識別情報を実行内で共有

- 作成日：2026-10-03
- 状態：完了（固定原本の処理。全内容変更の検出保証とは別）
- 比較元コミット：6bfadef

## 読者向け概要

原本全体のSHA-256は、使った記録のバイト列を識別する値です。短区間ごとに数十GB以上の原本を再読取すると、必要な区間だけを読む工夫が活きません。一回の実行では固定原本からSHAを最初に計算し、区間間で共有します。設定JSONは小さく、工程ごとに内容を確認します。

## 1. 目的・対象範囲

同じVDIFの区間列で全原本SHAの読取を一局一回へ減らすこと。manifest、時計、観測設定、局VDIFをまとめて識別し、処理途中で検出した入力変更を完成から除きます。単区間も同じ入力確認を行います。

## 2. 完了条件

- 任意のSHAや前回のcacheを信頼せず、今回の原本から計算する。
- 工程前後・区間間、同容量変更、ファイル置換、参照先変更を検証する。
- 従来と同じ相関値を確認し、実際の全SHA読取回数・容量を記録する。
- source/wheel検証、レポート、公開前確認、匿名コミットを実施する。

全条件を実施しました。statに表れないVDIF変更は下記の制限として残します。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/input_identity.py`：毎回原本から構築する実行内の識別object。manifest/clock/観測設定と各VDIFのSHA、容量を保持します。公開summaryに個人のローカルパスを含めません。外へ返す辞書はcopyです。
- `closure_pipeline.py`：単区間の識別と工程ごとの確認。内部APIで構築済みobjectを共有できますが、任意のSHA辞書は拒否し、入力参照先と現在の設定を照合します。CLI/GUIにSHA省略の入力はありません。
- `sequence.py`：一回作った識別objectを各区間へ渡します。参照先・device/inode・容量・mtime_ns/ctime_nsを確認し、小容量JSONはSHAも確認します。最終合成後の変更も拒否。
- `apps/correlator/tests/test_input_identity.py`：同容量書換、mtime復元、同バイト置換、symlink変更、hash計算中の変更、単区間途中停止、検出限界を検証。
- `workflows/input_identity_validation.py`：原本SHAの実読取回数・容量を数え、段階032の保存配列と比較。
- `tools/verify_sequence_installed.py`：checkout外の導入CLIでも識別情報と配列を確認。
- [観測手順](../guide/04-observation.md)・[インターフェース規約](../../interfaces/closure-pipeline.md)を更新。

## 4. 検証条件・結果

### 開発中に見つかった問題

最初のstatだけの実装では、同容量で書換えた小JSONのmtimeを元へ戻す試験のうち2件を見逃しました。短時間の書換がWSLのctime精度にも表れないケースです。小さな設定JSONを工程ごとに内容SHAでも比較するよう修正し、最終的な識別試験12件は成功しました。

大きなVDIFは工程ごとに全読取しないため、すべてのstat値が同じに見える変更を保証して検出することはできません。全statを固定値として返す単体試験でVDIFを書換え、変更を見逃す境界を明示しました。この試験を「変更を検出できた」とは数えていません。

### 配布と数値

Python 3.12.3、NumPy 2.5.1、SciPy 1.18.0、Astropy 7.2.2、Baseband 4.3.0。BLAS thread数1です。

| 検証 | 実測結果 |
| --- | --- |
| source全試験 | 181成功、124.06秒 |
| wheel導入後の全試験 | 181成功、125.2秒 |
| 既知の非推奨警告 | 各14968件。BasebandのNumPy shape変更、Starlette TestClient。未修正 |
| pip check | 問題なし |
| checkout外の導入CLI | 3区間完了、原本VDIFの全SHA読取4回、旧相関配列との最大差0 |

段階032の4局・1.6秒の点源＋雑音VDIFを再利用しました。pilotは0.512秒、各画像積分0.3秒、3区間の露光0.9秒です。新処理の相関値・重み・uvw・有効露光・power/SK診断・時刻・周波数の全数値配列と整数flag/countは保存済み参照と完全一致しました。原本SHAも同じです。

| 全原本SHAだけの読取 | 旧3区間方式を再現 | 新しい区間列の実測 |
| --- | --- | --- |
| VDIFの全読取回数 | 12回 | 4回 |
| VDIF読取容量 | 78,950,400 byte | 26,316,800 byte |

設定JSONのSHA確認は新処理で111回、合計104,747 byteでした。これは原本全読取とは分けて記録しています。旧SHA部分の時間0.02185秒、新SHA部分0.00697秒、新処理全体23.62秒でした。旧処理全体を今回再実行した時間ではなく、cacheも制御していない単発測定なので、総処理の速度向上率には換算しません。

画像探索は一初期値・100反復の動作確認で、反復上限に達しました。相対flux1とADC²の入力単位を確認した試験で、画像形状の合格試験ではありません。

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.input_identity_validation \
  --manifest outputs/stage032-sequence-final/input/manifest.json \
  --clock-model outputs/stage032-sequence-final/input/clock.json \
  --reference outputs/stage032-sequence-final/sequence/synthesis/visibility.npz \
  --output outputs/identity-new
```

全試験は `python tools/run.py pytest -q` と導入後の `python -m pytest -q` で実施しました。[数値と実読取](../../validation/runs/stage034/summary.json)、[導入CLI](../../validation/runs/stage034/installed.json)、[検証・wheel識別](../../validation/runs/stage034/verification.json)を保存しています。大容量原本と詳細ログはGit管理外の `outputs/` にあります。

## 5. 制約・未解決事項

- 収録終了後の固定原本を使います。収録中の追記や上書きを前提にした方式ではありません。
- VDIFの全stat値を保持する変更、時刻精度に表れない変更、特別なファイルシステム操作は検出を保証しません。Python callerは信頼した開発コードで、objectはsecurity境界ではありません。
- 共有は同一実行内のみ。別実行では原本から再計算します。原本SHAと全VDIF headerの正常性は別です。
- 常時の全内容再確認やsnapshot filesystemは未実装。長時間・実ストレージでのthroughputも未検証。
- 局周波数差は各pilot内で一定、sample時計は与えた線形モデル、Closureは高SNR近似です。実OCXO・実受信機・Cas Aの良好画像化の確認には進んでいません。

## 6. 次段階

pilot内で局周波数差が変わると、一定rateの補正がどれだけ信号を残すかを検証します。短い区間への分割と、変動の診断を検討します。
