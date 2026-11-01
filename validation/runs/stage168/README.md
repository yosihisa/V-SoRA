# 段階168の検証記録案内

[レポート](../../../docs/reports/168-sigmf-reader-api.md)と[限定API契約](../../../interfaces/sigmf-input.md)を参照。手順と合否のみ公開し、録音・提供metadata・派生配列・科学summary・ブラウザ画像はGitへ載せない。

## 入力と再実行

[取得配置案内](../../../docs/guide/public-voltage-data.md)に従ってCAMRAS原本を `data/raw/public/camras-crab/` に置く。ci16_le・400万complex sample・供給Fs20MHz。原本/metadataのSHAはreport、receiptを含む実行前3SHAは管理外記録へ保持する。

```bash
.verification-venv/bin/python tools/run.py workflows.public_sigmf_api_validation \
  --input data/raw/public/camras-crab --output outputs/public-sigmf-api-check
```

新しい出力先を使う。installedは対象wheelを別prefixへ導入し、そのPythonでcheckout外cwd/PYTHONPATHなしにworkflowの絶対pathを指定する。独立参照helperはcheckoutに必要だが製品API利用には不要。

## 正式選択と記録

新SigMF/新SampleBuffer/旧VDIF/clock/seek/clock入力契約の120対象と、両collect2392/全2392成功、全回帰各30220警告を記録。新64試験を含むがtarget/fullを独立試験として加算しない。

全800万成分の独立復号、供給時刻1ns以内、166固定4窓×seek/順次8条件の有限作用、source/installed/166の17配列一致を確認。新wheel/pipcheck、104製品file＋4assets全byte、旧151 prefix103＋4保持、checkout外API、両実Chromium各28条件/56 JSON、上書き拒否2。全正式worker初回成功。MC/MCSE・実複数局相関/Closure/画像は対象外。

管理外記録は `outputs/stage168-preparation/` の `purpose-fixed.md`、`frozen.json`、`input-files.json`、`workers.json`、各log、`verification-private.json`、`progress.json`。補助準備失敗は `auxiliary-preparation-error.json`、全worker終了後の重複入力索引は `gui-input-sha-supplement.json`。原本studyと実GUI結果は `outputs/stage168-source-study/`、`outputs/stage168-installed-study/`、各 `stage168-*-browser/`。wheelは `outputs/stage168-wheel/`、独立prefixは `outputs/stage168-installed-venv/`。

単局ADCと供給時刻の契約照合であり、実時計精度・天体検出・RFI品質・画像復元の成功を意味しない。全データをGit管理外に保持する。
