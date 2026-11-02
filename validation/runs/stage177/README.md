# 177：明示SigMF参考画像の方法記録

[段階report](../../../docs/reports/177-sigmf-reference-image.md)。ここには文章だけを置く。原本/提供metadata/変換電圧/科学JSON/配列/画像/図はGitへ追加しない。

## 入力と手順

174で固定した `outputs/stage174-input` の相互に異なる模擬4局と、`outputs/stage174-source-study` の完成2窓shardを保持する。初期入力は新取得/再生成/再変換せず全SHAを照合する。131原本は76SHAの照合だけ。CAMRAS単局を画像用複数局に複製しない。

旧176 installed `image_synthesis` に保存SigMF/VDIFの各2窓を渡し、同じstarts1/max_iterations100/prior240/entropy.01/TSV.0001で比較参考画像を各1回保存する。旧SigMFはunverified historical referenceであり、新入口の認証済み実観測ではない。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_reference_image_validation \
  --input outputs/stage174-input --saved outputs/stage174-source-study \
  --baseline outputs/stage177-old176-baseline --output outputs/stage177-source-study
```

出力先は未存在directoryを使い、再実行は別directoryへ保存する。workflowはsource/installedの両方で実施する。installed workflow自身はcheckoutの比較helperを使うが、製品API試験はcheckout外でhelperをimportせず実行し、全product module originとbyteを確認する。

## 比較契約

各2窓の全NPZ fieldとroot科学JSONを保存174へ照合する。窓rootの共有identity累計だけは旧比較の会計表示として区別する。新SigMF画像/Closure/科学JSONは旧176参考、新VDIFは旧176既定画像へ一致させる。追跡input_sha256は各実fileへ確認してから比較外とし、source照合の診断/scopeとruns.elapsed_sだけを区別する。他の数値・byte・optimizer statusを捨てない。新source/installedの全NPZ fieldはmetadataを含め一致させる。

NPYはfinite/非負/sum1を1e-12以内、FITSは自身のchecksum/DATASUM、BUNIT=1/pixel/FLUXREF=ARBITRARY/POSREF=ASSUMED、画素はNPYのfloat32と一致することを検査する。FITS生成時刻のbyte一致では判定しない。全optimizer statusを残し、iteration-limitを収束済みとしない。

独立参照は32²画素/w項を含む明示Fourier和、保存baseline weightからのvarianceと行行列のfull covariance、numpy solve、wrapped phase/logampと既存3正則化の別計算。productの選択した42行を条件とする。固定2probeのobjective RTOL1e-10/ATOL1e-8、mean0/norm1のsin/cos4方向ずつ、h1e-5の独立中央差分とanalytic gradientをRTOL1e-5/ATOL1e-7で比較する。MCSEなし。実FFT独立性や未知の実noise分布、画像精度を検査していない。

## 正式運用

source/tests/tools/workflows/private helpers/入力を凍結し、正式中に変更しない。両対象/collect/full、新wheel/pipcheck/105製品+4assets全byte、旧151/168/169/171/172/173/174/175/176 prefix保護、checkout外API、sequence/synthesis実CLI、非上書き拒否、両実Chromium28既存条件を選択する。175/176のdefault/verified merger全44field/JSONの別回帰も行う。通常GUIはHTTP/api/jobsをread-only確認するだけで更新/再起動しない。

全worker終了後だけ記録を確定する。失敗時はlog/部分出力/凍結表を保持し全選択を別attemptで再実行、成功を合算しない。参照worker120秒/追加peak256MiB/科学保存64MiB、full/GUI900秒、stage3600秒/attempt・全7200秒、全保存2GiB/空き10GiB reserve。正式結果と失敗記録はreportへ記載する。
