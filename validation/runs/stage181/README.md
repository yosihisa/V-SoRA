# 181：偏波別LBA複素帯域viewの検証

[レポート](../../../docs/reports/181-lba-complex-band-view.md)と[契約](../../../interfaces/lba-complex-band.md)を参照。固定178原本/receipt/保存levelsを使い、新取得・原本生成・既存fileの書換えは行わない。派生complex array/科学JSON/全SHA/失敗log/凍結は管理外へ保存する。

```bash
.verification-venv/bin/python tools/run.py pytest \
  packages/formats/tests/test_lba_complex_band.py \
  packages/formats/tests/test_lba_fragment_reader.py \
  packages/formats/tests/test_sigmf.py packages/formats/tests/test_vdif.py \
  tests/integration/test_public_lba_fragments.py -q
.verification-venv/bin/python tools/run.py workflows.lba_complex_band_validation \
  --input data/raw/public/difx-lba-v177a \
  --baseline outputs/stage178-source-study --output outputs/stage181-source-study
```

未存在の出力directoryを指定する。元header/Fs/offset/偏波を保持し、各偏波を別々に処理する。quarter-band NCOは元source index mod4を使用、factor2/129tap Kaiser8.6/cutoff7/32/DC gain1を固定し、両側64sampleの完全supportだけを返す。actual_rate/局ID/RFは未知のままで、R/LをI/Qにしない。

独立係数はsinc/Kaiserの有限式、独立出力はtapごとの明示和。固定48窓をRTOL1e-11/ATOL1e-8 code-unitへ照合する。8偏波の全有効16776192sampleをchunk4096/16384で各一巡しstream SHAを比較する。同じ有限標本の再実行で、独立観測試行ではない。

別の合成decoded tone14条件/各257出力はdesired+mirror両項の有限応答へ照合する。固定mu=k/16,k=-3..3の7点でpass gain誤差と鏡像gain各1e-3以内を要求し、連続帯域のsup保証とはしない。合成toneは内部operator入力で、収録2bitデータではない。

保存fieldはbounded-band.npzの48windowとoperator-probes.npzの5array（係数/独立係数/tone actual/tone expected/7点response）、計53。source/installed全fieldと方法JSONを厳密一致、比較除外はwall_s/import_current_RSS_bytes/peak_RSS_bytes/conservative_additional_peak_bytesだけ。MCSEなし。constructor hash計数は元reader側だけでworkflow原本再照合/総I/Oとは分ける。

両新source/installed対象/collect/full、新wheel/pipcheck/107製品+4assets全byte/module origin/deps、checkout外helper不要API・実workflow CLI/既存inspect-sigmf実CLI、両実Chromium28保存診断条件を正式選択する。新LBA/SigMF画面ではなく通常GUI151は更新・再起動しない。旧prefixと179初回archiveは各旧wheel byteを保持する。

事前の参照添字誤読10失敗/95成功はtestだけを訂正し105成功、その後view context guardを追加して最終110成功。旧test/product/log/失敗pytest一時/studyを保持し、最終productでstudyを再実行した。初回成功を合算しない。正式中はsource/tests/tools/workflows/helpers/入力を固定し、修正は全worker終了後だけ、失敗/部分/freezeを保持して全選択を再実行する。

worker120秒/追加peak256MiB/科学保存各64MiB、full・GUI900秒、attempt3600秒/全7200秒、全attempt/pytest一時/補助/公開textを含む4GiB、空き10GiB reserve、公開512KiB。worker境界と最後の保存監査を連続FS peakと区別する。原本/提供metadata/派生array・科学JSON・図をGitへ公開しない。新相関/Closure/画像study/MC0。

正式初回：両対象165成功/41warning、collect/full各2634成功/39404既存種別warning/除外0。53field/方法JSON厳密一致、107製品+4assets全byte/3module origin/44依存版/pipcheck/checkout外API・実CLI、両実Chromium各28条件/56JSON/672行/JS0/外部0/日本語390px。19worker全終了、非上書き2return1は意図した拒否。全worker終了後に所有・lock不在・正式時刻内を確認した成功pytest一時出力だけを削除し、事前失敗のpytest一時/log/旧code/studyは保持する。
