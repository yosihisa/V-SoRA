# 段階006：CASAによる独立互換確認

- 作成日：2026-10-02
- 状態：完了（単一XX・continuum限定）
- 比較元コミット：dd1173a

## 1. 目的・対象範囲

自分のwriter/readerが同じ誤りを持っていても検出できるよう、CASAでFITS-IDIを読込み、偏心点源の画像位置・明るさを独立確認する。Windows収録、実観測、主ビーム補正は対象外。

## 2. 完了条件

CASAがFITS-IDIを受入れ、visibility/uvw/時刻/局番号が期待値と一致する。点源の東西・南北と明るさが正しい。入力逆分散重みを明示的に復元して確認する。全既存テストが成功する。

## 3. 実際に行った作業

- `workflows/export_casa_fixture.py`：西48秒角・北32秒角、1000 Jyの点源を独立検証入力に使用。
- `tools/verify_casa.py`, `tools/run_casa.py`：隔離CASA環境でimport、列比較、重み復元、dirty画像化。
- `packages/formats/.../fitsidi.py`：**v1ではCASA画像が反転**したため、保存FLUXを内部visibilityの共役へ変更したv2を定義。UVWの負符号は維持。内部readerはv1/v2を識別する。
- DATE/TIMEは二部分JDを保存し、大きいJDの減算による約20 μsの損失を解消。直径未設定は0。J2000を明示してCASAへ入力。
- `interfaces/fitsidi-profile.md`：符号・重み・旧形式の制限を更新。
- `docs/design/casa-environment.md`：CASA 6.7.6.14、Measure tables、局所的OpenSSL互換対応を記録。OSライブラリは変更していない。
- `.gitignore`, `.gitattributes`：CASA環境・ログ・MSを除外し、FITS/NPZ/PNGをbinaryとして扱う。

## 4. 検証条件・結果

Python 3.12、CASA 6.7.6.14。4局・10時刻・60 baseline行の点源と、段階005のCas Aをv2へ再出力した8局・16時刻・448行で確認。

```sh
python tools/run.py pytest -q
python tools/run.py workflows.export_casa_fixture --output outputs/fixture
python3 tools/run_casa.py tools/verify_casa.py --input outputs/fixture/point.fits --expected outputs/fixture/expected.npz --output outputs/casa-check --image
```

| 項目 | 点源 | Cas A |
| --- | ---: | ---: |
| visibility相対誤差 | 2.30e-8 | 0（既保存float32値との比較） |
| 負符号変換後uvw相対誤差 | 9.94e-17 | 8.95e-17 |
| MS時刻差 | 0秒（MJD double基準） | 0秒（同基準） |
| 局番号 | 一致 | 一致 |
| import直後の重み倍率 | 245760000 | 524288 |
| 重み復元後相対誤差 | 0 | 0 |

点源の期待pixel[67,66]に対し観測[67,66]、peak **1000.000732 Jy/beam**、相対誤差7.32e-7。修正前は[61,62]であり、外部確認で符号問題を検出した。既存テスト **33件成功**、Basebandの既知DeprecationWarning 37件。

記録：[点源summary](../../validation/runs/stage006/point-summary.json)、[Cas A summary](../../validation/runs/stage006/casa-summary.json)、[v2点源入力](../../validation/runs/stage006/point-v2.fits)、[v2 Cas A入力](../../validation/runs/stage006/visibility-v2.fits)。CASAログ/MSはローカル`outputs/stage006-*`に保存しGit管理外。

## 5. 制約・未解決事項

- 段階005の保存FITSはv1でありCASAへ直接渡せない。今回のv2再出力を使用する。
- CASA importfitsidiの重み初期化は入力逆分散をそのまま維持しなかった。検証ツールではexpected.npzから復元したが、汎用converterへの実装は残る。
- 未登録望遠鏡VSORA、独自VSORA_META、主ビーム未定義の警告あり。画像位置確認に使用したが主ビーム補正は検証していない。
- AIPS、複数偏波・複数channel、実受信IQ、CASAによるCas AのCLEAN復元はこの段階では未検証。
- OpenSSLライブラリは互換確認のため構築したがOpenSSL自身のtest suiteは未実施。暗号機能の評価を完了扱いにしない。
- 時刻差0は保存されたMJD doubleとの一致であり、真のUTCやGPS同期精度の実測ではない。

## 6. 次段階

受信機間の未知の位相・遅延・周波数差と利得を、時間・周波数分解visibilityから推定する。帯域平均前の情報を保持し、検出失敗や曖昧性を明示する。
