# 178：公開4局断片の取得・表現検証

[report](../../../docs/reports/178-public-lba-fragments.md)。原本/提供metadata/配列/科学JSON/図はすべて管理外。ここに置くのは方法・合否の文章だけ。

## 配置と再現手順

[公式DiFX配布案内](https://github.com/difx/difx/wiki/datasets)と配布READMEのtesting/verification用途を確認する。個別データライセンスの明示は確認できず、コードGPLをデータ全般の許諾へ転用しない。ローカルな非再配布検証に限定し、account/job/人への連絡を行わない。

未存在directoryへ次の順で実行する。probeは旧16byte timestamp headerとtar indexだけを保存し、取得planを生成する。planには元offset/供給時刻/局ID/偏波/SIZE/MDTM/header SHAを保持する。今回取得したcase専用であり、一般のLBA 32/64MHz配置への対応ではない。

```bash
.verification-venv/bin/python tools/run.py workflows.public_lba_fragments \
  --probe --output outputs/lba-v177a-headers
.verification-venv/bin/python tools/run.py workflows.public_lba_fragments \
  --acquire-plan outputs/lba-v177a-headers/acquire-plan.json \
  --output data/raw/public/difx-lba-v177a
.verification-venv/bin/python tools/run.py workflows.public_lba_fragments \
  --input data/raw/public/difx-lba-v177a --output outputs/lba-v177a-validation
```

空き10GiB/取得client byte32MiB上限を維持する。原tar160010240byteや各member40000016byte全体を取得せず、共通供給UTCから.262144秒の各payload1048576byteだけを保存する。header/payloadを別に保ち、元headerを書き換えない。原archive/member full SHAはnullのまま、取得断片SHAだけをreceiptへ残す。FTPはREST開始offsetから所定byteをreadして接続を閉じるため、TCP/wireやserver先行送信の全byteはこの計数に含まない。

既存出力/.partialを上書きしない。失敗時は部分受信、ログ、failure/transfer receiptを保持し、再実行を別attemptとして識別する。再取得の必要がなければ正式再実行は固定断片を再利用する。録音・metadata・派生物へgit add -fを使わない。

## 固定数値検査

4局/2pol/8MHz公称/real2bitの全16777216成分をvector bit-planeと別u16 scalar法へ厳密一致。全4194304payload byteをrepackして厳密一致。標準s16 codeを物理電圧と呼ばない。コード列の情報は保存するが、収録時2bit量子化以前の波形は復元しない。

固定index 0/262144/524288/1048576から各N256、全32rFFT/129binをcode/32768の固定解析scaleで独立cos/sin有限和へ比較。RTOL1e-11/ATOL1e-8、MCSEなし。統計的独立性、天体検出、実相関/Closure/画像の検証ではない。

正式は両12offline unit、両study、公開live probe/生成plan一致、非上書き3、旧製品105+4/全旧prefix byte、13176SHA/過去入力SHAを選択。時間/メモリ以外の科学fieldを環境間で除外しない。新製品API/full/wheel/install/pipcheck/browserは実行しない。現製品基準177の引用を今回の新合格へ足さない。全失敗、最終選択2の結果と容量はreportに記載する。
