# 182：明示clockモデルによるLBA複素帯域query

[レポート](../../../docs/reports/182-lba-clocked-band-query.md)と[契約](../../../interfaces/lba-clocked-band.md)を参照。

```bash
.verification-venv/bin/python tools/run.py pytest \
  apps/correlator/tests/test_lba_clocked_band.py \
  apps/correlator/tests/test_clock.py apps/correlator/tests/test_clock_input_contract.py \
  packages/formats/tests/test_lba_complex_band.py \
  packages/formats/tests/test_lba_fragment_reader.py \
  packages/formats/tests/test_sigmf.py packages/formats/tests/test_vdif.py \
  tests/integration/test_public_lba_fragments.py -q
.verification-venv/bin/python tools/run.py workflows.lba_clocked_band_validation \
  --fixture outputs/stage182-fixed-input \
  --real-input data/raw/public/difx-lba-v177a --output outputs/stage182-source-study
```

新fixtureはheader `20200102:030405` + newlineの16byte、payload8192byteのi番目=(73*i+19)%256。原本観測ではない人工fixtureで、source/installedへ同じ固定fileを渡す。元offset1/R,L/8MHzを固定。fixtureの生成・配置を行う場合はcodeから同じbyteを管理外へ作り、新たな空のstudy出力directoryを選ぶ。

2clock/RFモデル×2偏波×3固定query窓の12case、各129点。whole/分割[1,7,31,90]厳密一致、scalar decode/129項FIR/65項補間/位相の独立有限参照へRTOL1e-9/ATOL1e-5 code-unit、Fraction exact binary座標へATOL1e-9 sample。MCSEなし。source/installed60field（actual/expected/valid/source_positions/query_times各12）と科学JSON全一致、除外はwall_s/import_current_RSS_bytes/peak_RSS_bytes/conservative_additional_peak_bytesだけ。

invalid区間[1050,1052)のsupportを伝播し、invalid出力は0/valid=false。実4局はunknown actual clock/RFでquery前に拒否し、実原本のcomplex query0。新実相関/Closure/画像study/MC0。人工の供給clockを実原本へ代入しない。

両新source/installed対象/collect/full、wheel/pipcheck/108製品+4assets全byte/module origin/44依存版、checkout外helper不要API/実workflow CLI/既存CAMRAS inspect-sigmf実CLI、両実Chromium28保存診断条件を正式選択する。通常GUI151更新/再起動0、新LBA画面ではない。旧全prefixと179初回archiveを各旧wheel byteへ照合する。

事前study1の1点分割差はscalar phase演算へ揃え、入力/許容は不変で全選択を再実行。旧code/test/log/部分を保持し、最終121対象成功/新study成功を正式と合算しない。正式中code/tests/workflows/helpers/入力を固定し、修正は全worker終了後だけ、失敗/部分/freezeを保持して全選択を再実行する。

全attempt/全pytest一時/補助/公開textを含む4GiB、空き10GiB、study追加peak256MiB/保存各64MiB、worker120秒/full・GUI900秒/attempt3600秒/全7200秒。worker境界と最終監査を連続FS peakとしない。今回の週間reserve使用はユーザー許可の1枠だけ、追加reset0、絶対終了11月4日05:05:16 JSTを延ばさない。原本/metadata/派生array・科学JSON・図はGitへ公開しない。

最終attempt2：両対象273成功/2857既存種別warning、collect/full各2694成功/39404既存種別warning/除外0。60field/科学JSON/API JSON厳密一致、108製品+4assets全byte/6module origin/44依存版/pipcheck/checkout外API・実CLI/両実Chromium各28条件/56JSON/672行/JS0/外部0/日本語390px。19worker全終了、非上書き2return1は意図した拒否。初回はinstalled studyの公開helper import経路不足で停止し、全終了/証跡保持後にCLI経路だけを訂正して全選択を再実行。製品/入力/許容を変えず、初回成功を合算しない。全終了後に所有・lock不在・正式時刻内を確認した成功pytest一時だけを削除し、初回archiveと全失敗証跡を保持する。
