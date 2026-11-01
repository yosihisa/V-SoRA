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

## 後続候補の扱い

- [MWA取得手順](https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24973422/Data%2BProcessing%2BDocumentation)：アンテナ別電圧を得られる候補。観測ID・公開可否・利用条件・最小取得容量を確定してから選ぶ。SMARTの旧VCSとMWAXの形式/容量を混同しない。
- [CHIME/FRB Baseband Catalog 1](https://chime-frb.ca/catalogs/basecat1)：較正・ビーム合成済み電圧の候補。個別アンテナのrawとは区別し、配布ファイル一覧・容量・利用条件の確認を先に行う。

164では両者の本体取得、アカウント作成、取得ジョブ投入を行っていない。大容量の一括取得を自動化せず、空き容量と具体的な検証目的を先に固定する。
