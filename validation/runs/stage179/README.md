# 179：LBA fragmentの偏波明示・有界API

[レポート](../../../docs/reports/179-lba-fragment-reader-api.md)と[契約](../../../interfaces/lba-fragment-reader.md)を参照する。入力は[178](../stage178/README.md)の変更しない原本fragment/receiptと完成study。再取得、原本生成、変換、相関、画像fitは行わない。元member/archive全体のSHAは未知のまま保持する。

```bash
.verification-venv/bin/python tools/run.py pytest \
  packages/formats/tests/test_lba_fragment_reader.py \
  packages/formats/tests/test_sigmf.py packages/formats/tests/test_vdif.py \
  tests/integration/test_public_lba_fragments.py -q
.verification-venv/bin/python tools/run.py workflows.public_lba_reader_validation \
  --input data/raw/public/difx-lba-v177a \
  --baseline outputs/stage178-source-study --output outputs/stage179-source-study
```

新しい出力directoryを指定する。各局2偏波をchunk4096で読み、全16777216成分を保存178 levelsへ厳密一致、8偏波のstream SHAを照合する。固定6seek×2偏波×4局=48arrayを保存する。全量decodeの保持を製品descriptorへ持たせず、read最大32770byte/返却最大131072byteを確認する。これはwhole process memoryやthroughputの保証ではない。

旧workflowの互換検査は次を別出力へ行う。旧32FFTを同じ有限標本で再検査する回帰で、新科学試行として加算しない。

```bash
.verification-venv/bin/python tools/run.py workflows.public_lba_fragments \
  --input data/raw/public/difx-lba-v177a --output outputs/stage179-source-legacy
```

保存178との全10field/科学JSONの一致を要求し、比較除外は `wall_s/import_current_RSS_bytes/peak_RSS_bytes/conservative_additional_peak_bytes` の4項目だけ。new source/installedは48field/summary/API JSONを全一致させる。新installedは別prefix、新wheelを使う。checkout外APIはworkflow helperをimportせず、新purelibから製品を読むことを検査する。既存inspect-sigmf実CLIも固定CAMRAS pairで回帰し、新LBA CLIと扱わない。

両新collect/full、wheel全byte/pipcheck/依存版/module origin、両実Chromium28既存条件も正式選択に含む。GUIは保存模擬診断の回帰で、新LBA画面ではない。通常GUI151や旧prefixは更新・再起動しない。

失敗log/変更前test/凍結/数値出力/配列/全SHA/資源計測は `outputs/stage179-preparation` と `outputs/stage179-*` の管理外に保存。原本と提供metadata、派生配列/科学JSON/図をGitへ公開しない。整数厳密一致/MCSEなし。名目時刻/供給偏波文脈の検査で、実clock/物理電圧/天体検出/fringe/画像検証ではない。

正式attempt1の数値/互換選択は成功したが、完了時に所有pytest一時出力を含めると2239425393byteとなり、固定2GiBを少なくとも91941745byte超過した。検査helperが一時出力を含まなかった不備を記録した。全worker終了後、成功したpytest一時出力だけを削除し、初回の全log/科学出力/freeze/wheel/prefix/helpersは `outputs/stage179-formal-attempt1` へ保持した。製品・原本・数値許容は不変で、保存4GiB（両attemptと新pytest一時出力を含む）/空き10GiB/全7200秒へ正式前に改訂し、全選択をattempt2として再実行した。各worker前後に保存量を検査し、初回成功を合算しない。境界での保存量検査は連続的なfilesystem peak測定とは異なる。
