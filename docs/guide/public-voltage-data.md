# 公開電圧データの取得と配置

公開実記録で入力処理を進めるための手順。観測者側のRTL-SDR/OCXO構成は未決定のままであり、公開記録をその装置の実機検証へ読み替えない。

## 最初の原本：CAMRASのかにパルサー

[公開一覧](https://data.camras.nl/giantpulses/)の `crab-giantpulse.sigmf-data` と同名の `sigmf-meta` を使用する。[メタデータ](https://data.camras.nl/giantpulses/crab-giantpulse.sigmf-meta)の説明は Crab pulsar giant pulse。提供者は Stichting CAMRAS、Maxwell Fine、Tammo Jan Dijkema。個別メタデータの利用条件は [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。再配布時には個別条件を再確認する。本リポジトリから原本・メタデータ・派生データは再配布しない。

プロジェクトのルートから、既存の検証用Python環境で実行する。

```bash
.verification-venv/bin/python tools/fetch_camras_crab.py --directory data/raw/public/camras-crab
```

初回取得で確認した容量は本体16,000,000 byte、メタデータ1,954 byte。取得ツールは合計32 MiBを上限とし、開始・途中で10 GiBの空き容量を確保する。既存の配置先は上書きせず拒否する。失敗時は `.partial` と `acquisition.json` を保持する。再試行する場合も失敗記録を消さず、別の配置先を選ぶ。

配置は次のとおり。全て既存の `/data/raw/` ignore対象である。`git add -f` を使わない。

```text
data/raw/public/camras-crab/
  crab-giantpulse.sigmf-data
  crab-giantpulse.sigmf-meta
  acquisition.json
```

`acquisition.json` は取得URL、UTC、HTTPの容量/ETag/Last-Modified、実byte数、SHA-256、空き容量、完了状態を保存する。取得後に次を確認する。

```bash
git check-ignore data/raw/public/camras-crab/crab-giantpulse.sigmf-data
git check-ignore data/raw/public/camras-crab/crab-giantpulse.sigmf-meta
sha256sum data/raw/public/camras-crab/crab-giantpulse.sigmf-data
```

2026-11-01初回取得時の本体SHA-256は `e12a408af4d963802623a95ee732c20b0b6b0cbf787454f5b10753d6d04f992e`、メタデータは `42878700f4cc91c4cda249ec1d958cea6c7e78fc1b13f3af714f654956f4f188`。提供元の公表checksumとの照合ではなく、こちらの初回取得byteを識別する値である。将来内容が変わった場合は同じ入力として合算しない。

## ローカル検証と保存先

```bash
.verification-venv/bin/python tools/run.py workflows.public_iq_validation \
  --input data/raw/public/camras-crab --output outputs/public-iq-check
```

`outputs/public-iq-check/` に有限スペクトル/電力の配列、科学summary、実行環境を保存する。これらもGit管理外。新しい出力先だけを使い、原本を編集しない。waveform・metadata・NPZ・図・変換電圧はアップロードしない。公開するのは取得配置方法、検証コード、方法と合否の文章だけである。

この記録は単局の `ci16_le`（I/Q各16 bit）、供給Fs20 Msamples/s・中心410 MHz・公称0.2秒。FFTの数値整合は天体検出の再現や時計精度の測定ではない。小数秒のcapture日時と別名の日時欄が併存し、意味・精度の照合は未実施。現行VDIFアダプターの4096sample/frame条件にはFsが合わず、さらに現アダプターは整数秒開始を要求する。日時・Fsを仮の値に置き換えて変換しない。単位ADCをJyへ読み替えず、単局を複製して基線やClosureを作らない。

## 小数秒時刻を保つVDIFの限定参照

[165の検証](../reports/165-public-iq-vdif-time.md)は、検証用Baseband writerで4,000sample/frame・5,000frame/sへ保存し、既存の `iter_vdif_frames` で読む。供給Fs・capture時刻・sample順を保持し、resample/drop/padを行わない。製品writerの整数秒制約や、manifestの4096sample/frameという記載を変更するものではない。

```bash
.verification-venv/bin/python tools/run.py workflows.public_vdif_validation \
  --input data/raw/public/camras-crab --output outputs/public-vdif-check
```

Linuxの検証環境で、存在しない出力先を指定する。`reference-only.vdif`（8,032,000 byte）、科学summary、3つのframe別配列、実行環境を `outputs/public-vdif-check/` に保存する。EDV0にはFsが格納されないため、供給Fs20 MHzと復号scaleはローカルsummaryと原本metadataから読む。station番号1はこの変換用の識別子で、実収録headerの局番号や新しい観測局ではない。

8 bit成分への変換は非可逆。scaleは全int16範囲から事前固定した9,088 ADCで、原本に合わせた利得推定ではない。全サンプルが独立量子化式へ一致しても、元の16 bit電圧と同じ値という意味ではない。低SNR科学解析用の標準変換として採用していない。元のSigMF原本を必ず保持する。

installed比較では既存wheel導入Pythonを使い、checkout外をcwdとし、PYTHONPATHを外す。workflowと既存の二つのhelperはcheckoutに必要である。製品moduleをsourceへ差し替えない。

```bash
project_root="$PWD"
(cd /tmp && env -u PYTHONPATH "$project_root/.verification-venv/bin/python" \
  "$project_root/workflows/public_vdif_validation.py" \
  --input "$project_root/data/raw/public/camras-crab" \
  --output "$project_root/outputs/public-vdif-installed-check")
```

変換VDIF・summary・数値配列もアップロードしない。初回失敗の出力を含む全ローカル容量と空きを確認し、失敗記録を削除して容量や成功件数を小さく見せない。

## 16bit原本と整列バッファの限定参照

[166](../reports/166-public-iq-samplebuffer.md)は、8bit化を避けて原本I/Qの値を保持し、既存SampleBufferの有限フィルター・補間を固定4窓で独立計算へ照合する。readerだけをworkflow内で置換するprototypeであり、製品session/CLIの形式追加ではない。供給Fsを名目mappingとして使い、実時計を推定しない。

```bash
.verification-venv/bin/python tools/run.py workflows.public_samplebuffer_validation \
  --input data/raw/public/camras-crab --output outputs/public-samplebuffer-check
```

存在しない出力先を使う。結果の17配列・科学summary・環境記録は全て `outputs/public-samplebuffer-check/` に保存する。installed比較の方法は上のVDIF参照と同じで、実行workflow名を `public_samplebuffer_validation.py`、出力先を別名へ変える。146・周期参照・164のhelperもcheckoutに必要。reader入口はint16値を正確に保持するが、FIR/補間の出力波形は変わる。実受信帯域・clock精度に対してその整列が科学的に適用可能かは未検証である。これらの出力もアップロードしない。

## 製品の限定SigMF APIを使う

[168で検証した](../reports/168-sigmf-reader-api.md) `SigMFRecording` と `SampleBuffer.from_sigmf` は[限定入力契約](../../interfaces/sigmf-input.md)に従う明示入口。検証用readerの置換を使わず、元のci16_le整数をcomplex128へ正確に読み、供給Fs・UTC-Z capture日時とsample順を保持する。全仕様対応や実時計較正を意味せず、session/相関CLIの形式追加でもない。

```bash
.verification-venv/bin/python tools/run.py workflows.public_sigmf_api_validation \
  --input data/raw/public/camras-crab --output outputs/public-sigmf-api-check
```

検証workflowは新しい出力先へ全成分照合のsummaryと17配列を保存する。全てGit管理外。installed比較は対象wheelを導入した環境のPythonを使い、checkout外cwd/PYTHONPATHなしで `workflows/public_sigmf_api_validation.py` の絶対pathを指定する。検証用の既存helperはcheckoutに必要だが、製品API単体の利用にはhelperは要らない。取得元の記録と供給metadataを保持し、出力電圧・数値配列・図をアップロードしない。

## 原本の組と期待SHAをCLIで照合する

取得後は `inspect-sigmf` で限定profile・原本pairを検査できる。新しい出力名を使う。

```bash
.verification-venv/bin/python tools/run.py vsora_correlator inspect-sigmf \
  --metadata data/raw/public/camras-crab/crab-giantpulse.sigmf-meta \
  --expect-metadata-sha256 42878700f4cc91c4cda249ec1d958cea6c7e78fc1b13f3af714f654956f4f188 \
  --expect-data-sha256 e12a408af4d963802623a95ee732c20b0b6b0cbf787454f5b10753d6d04f992e \
  --output outputs/public-sigmf-inspection.json
```

この機能を含むcommitからbuildしたwheel環境は `vsora-correlate inspect-sigmf` に同じ引数を渡す。上のSHAは初回取得byteを識別し、生産者公表checksumではない。metadata/dataの両SHAを新規計算し、片方だけの期待値・不一致・既存出力は失敗する。JSONはGit管理外。供給時刻/周波数と実測clockを区別し、局IDや天体品質を作らない。

同一処理内のdata変更検査にはstatの限界があり、全stat保持の変更は見逃し得る。[詳細契約](../../interfaces/sigmf-input.md)を確認する。このCLIは原本検査で、session/相関CLIへのSigMF入力形式追加ではない。

## 後続候補の扱い

- [MWA取得手順](https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24973422/Data%2BProcessing%2BDocumentation)：アンテナ別電圧を得られる候補。観測ID・公開可否・利用条件・最小取得容量を確定してから選ぶ。SMARTの旧VCSとMWAXの形式/容量を混同しない。
- [CHIME/FRB Baseband Catalog 1](https://chime-frb.ca/catalogs/basecat1)：較正・ビーム合成済み電圧の候補。個別アンテナのrawとは区別し、配布ファイル一覧・容量・利用条件の確認を先に行う。

164では両者の本体取得、アカウント作成、取得ジョブ投入を行っていない。大容量の一括取得を自動化せず、空き容量と具体的な検証目的を先に固定する。

[167の出典監査](../reports/167-public-voltage-provenance.md)で、MWA公式ライブラリの小容量VCS試験例は変更メタデータと試験生成波形であることを確認した。これを実観測の複数局記録として取得・利用しない。MWA ASVO/LOFAR LTAの取得手続きと、LWA実TBN論文・公開archiveも確認したが、今回採用できる独立複数アンテナ原本の直接取得先・最小byte・利用条件は未確定。観測ID・小容量・公開repoだけで実観測と認定しない。

## SigMFから時計整列相関へ進む条件

[171の明示session](../../interfaces/sigmf-session.md)で、異なる局ごとのci16_le原本pairと供給clockをdirect相関へ渡せる。公開CAMRASは単局なので局数が不足し、複製して実基線にはしない。供給epoch/Fs/RFとclock sample zeroを合わせる契約を満たす別局入力が必要。Windows受信機構成や実clockの推定が決まったことにはならない。

[検証workflow](../../workflows/sigmf_session_validation.py)は保存済み模擬4局を別の整数code尺度へ一度だけ派生し、独立有限作用と旧VDIFへ照合する。原本、派生SigMF、相関NPZ、summaryは全て管理外。実受信データの検証結果として流用しない。

## SigMFのpilot/rate/補正相関を検証する

[172の相関保存専用入口](../../interfaces/closure-pipeline.md#sigmfの相関保存専用入口)は、明示の供給clockと局ごとの原本pairから短いpilotを作り、保存した局rateで最終相関を補正する。画像/RML/sequence/GUIの形式追加ではない。公開単局データでは局数が不足する点を保ち、下の再現は保存済み模擬4局だけを使う。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_pipeline_validation \
  --prepare --input outputs/stage038-sequence/input --output outputs/stage172-input
.verification-venv/bin/python tools/run.py workflows.sigmf_pipeline_validation \
  --input outputs/stage172-input --output outputs/stage172-source-study
```

先に原本SHAを固定し、存在しない出力先へ一度だけ派生する。元038の生成を再実行せず、先頭70有効frameのpayloadを固定 `2*byte-255` の整数code尺度へ写す。元の供給scale/物理ADC/SEFDの較正ではない。原本・提供metadata・派生SigMF・相関NPZ・数値JSONは全て管理外に置き、アップロードしない。原本への取得配置指示と観測/模擬の区別は変わらない。

## 同じ原本のhashを再利用する検証

172の3pass検証workflowは172 commitの再現用。173以降は[再利用検証](../../workflows/sigmf_identity_reuse_validation.py)で、既に固定した172入力と完成studyを使う。再生成/再変換/再取得はしない。原本と旧studyの全SHAを先に固定する。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_identity_reuse_validation \
  --input outputs/stage172-input --baseline outputs/stage172-source-study \
  --output outputs/stage173-source-study
```

新しい出力先へ全結果を管理外保存する。独立有限作用は保持した172 helperを使うため、installed比較workflowにもcheckout helperは必要。製品API単体には不要。全数値field/科学metadataは保存172へ一致を要求し、変更を認めるのは原本追跡・SHA・その圧縮byte数だけ。byte数は実fileへ照合する。同じ有限標本であり、新しい実観測試行には数えない。これらの波形・metadata・科学JSON・配列はアップロードしない。

## 複数窓への接続

[174](../reports/174-sigmf-correlation-sequence.md)の明示correlation-only sequenceは、異なる局のSigMF原本がある場合に複数窓の補正相関を保存する入口。保存模擬4局で検証した。CAMRAS原本は単局のままで実基線は0。取得済みデータを変更・複製して局数を増やさない。画像付きpipeline/sequenceとGUIへのSigMF形式追加は含まない。

## 画像fitをせず補正窓を結合する

[175](../reports/175-sigmf-spectral-merge.md)の `vsora-synthesis --merge-only` は、保存された原本pair・clock識別を照合し、SigMF UTC9桁と全数値fieldを保って結合する。元rawの再hashや実時計較正は行わず、画像fitも実行しない。入力と結合NPZ、科学JSONは引き続き管理外に置く。

176では、merge-onlyへ原本manifest/clockと窓manifestを全指定した場合だけ、[freshな原本照合](../../interfaces/sigmf-spectral-merge.md#明示した元原本とのfresh照合176)を行える。既定175の保存情報だけの照合は維持する。元rawの生成・再相関や画像fitを行わず、recording間のdata/clock対応を検査する。原本からその数値が計算された履歴や実時計の正確さまで証明する入口ではない。

## 原本照合を保った参考画像の接続

[177](../reports/177-sigmf-reference-image.md)では、[明示参考mode](../../interfaces/sigmf-session.md#明示した高snr参考画像sequence177)だけを既存Closure/RMLへ接続する。174の異なる模擬4局と同じ固定波形を再利用してAPI接続を検査し、原本の生成・変換・取得は繰り返さない。このAPI試験の再相関は独立な観測試行ではない。実CAMRASは単局のままで、この画像の原本に複製して使わない。

検証workflowは [sigmf_reference_image_validation.py](../../workflows/sigmf_reference_image_validation.py)。旧176の参考画像、174の完成相関、独立した有限画素Fourier和・共分散solveと照合する。productのClosure行選択を条件にした代数検査で、未知実noiseや八条件の成立を示さない。画像・配列・科学JSON・原本/提供metadataはすべて管理外へ保存する。optimizerのiteration-limitを隠さず、形式接続と収束/画像精度を分ける。
