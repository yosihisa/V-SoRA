# 段階169：原本pairと検査CLIの記録案内

[レポート](../../../docs/reports/169-sigmf-identity-cli.md)、[限定契約](../../../interfaces/sigmf-input.md)、[取得配置方法](../../../docs/guide/public-voltage-data.md)を参照する。公開するのはコード・方法・合否の文章だけで、録音/提供metadata/派生JSON/波形/図はGit管理外。

```bash
.verification-venv/bin/python tools/run.py workflows.public_sigmf_identity_validation \
  --input data/raw/public/camras-crab --output outputs/public-sigmf-identity-check
```

新しい出力先を使う。`inspection.json` は製品APIの記録、`summary.json` は独立hash/供給項目との照合、`environment.json` はorigin/時間/メモリ。全て管理外。installedは新wheelのPythonでcheckout外cwd/PYTHONPATHなしにworkflowの絶対pathを指定する。API自体にはcheckout helperは不要。

実CLIは `vsora-correlate inspect-sigmf --metadata ...`。任意の `--output` は既存fileを拒否する。`--expect-metadata-sha256` / `--expect-data-sha256` は両指定のみ。原本pairの検査で、相関sessionへの形式追加ではない。

管理外記録は `outputs/stage169-preparation/` の `purpose-fixed.md`、`input-files.json`、`gui-input-files.json`、`frozen.json`、`workers.json`、各log、`progress.json`。preformal失敗/補助誤呼出と8合成例の時刻属性は `preformal-failures.txt` / `preformal-stat-granularity.json` に保持。正式source/installed原本記録は各 `outputs/stage169-*-study/`、実GUIは各 `stage169-*-browser/`、新wheel/独立prefixは各 `stage169-wheel/` / `stage169-installed-venv/`。

全stat保持のraw変更は同instanceの境界で見逃し得る。metadataは再hash、rawは各instance1回全hashで別runにもcacheを継承しない。合成unit試験を実受信機の変更検出・時計精度の実測にしない。全正式結果はreportへ記録する。
