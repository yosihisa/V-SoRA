# 段階131：独立seedの短区間VDIF原本を固定4条件で準備

- 作成日：2026-10-26
- 状態：完了（原本生成と構造・再現照合。相関・画像化は未実施）
- 比較元コミット：b36e593e87ed87e743abe39b9350cfe54ff7f531（130）

## 読者向け概要

125〜129は同じ保存相関や無雑音の人工天空を使って画像側の違いを調べた。次に、短い積分と未知の局周波数差を処理できる条件へ戻るため、新しい模擬電圧の原本を作った。

同じ時刻・配置で、仮定SEFD1000/10000Jyを各2seed、4原本に固定した。SEFDは受信機雑音に相当するfluxで、小さい方が高感度の仮定である。sourceと導入済み計算部品で再生成し、全原本bytes・構造・境界復号が一致した。今回確認したのは原本を再現できることまでで、未知LOの取得、相関、画像復元の成功ではない。

## 1. 目的・対象範囲

1.42GHz、最大基線600m、8局、仮定Cas A flux1000Jy、2.048MS/s、8bit I＋8bit Q、4096複素sample/frame、1520frameの3.04秒を固定した。全条件の開始時刻は2026-10-02T10:00:00Z。別時刻のuv合成や一晩の連続観測ではない。

原本間で生成seedを変える。既存producerは同じ乱数器から電圧、gain、LOを作るため、seed変更は雑音だけの介入ではない。SEFDだけを変えた因果比較でもなく、固定した4条件の原本である。

## 2. 完了条件

原本のサイズと資源上限、seed/出力IDの重複拒否を事前固定する。4source＋4導入core workerで生成し、各環境の全48640 header、64境界frameの復号、全原本SHA、truth/来歴/単位・clock・scale、同じ出力先の拒否、全読込prefixを確認する。

観測側にはmodel=unknown、fluxなしとし、実seed・真値rate・天空は入力の外へ分離する。既存core/package/wheel不変、対象試験/実collect、レポート/索引/公開監査・匿名commit/pushまでを完了条件とする。全回帰を再実行しない場合は過去の実行を引用と明示する。

## 3. 実際の変更と生成条件

`workflows/independent_raw_matrix.py`に固定行列・資源preflight・独立worker・構造照合を追加した。実際の電圧生成は既存の`extended_fixture`を変更せず使う。導入側も同じcheckoutのworkflow helperを使い、数値部品を導入prefixから読み込む。helper自体をwheelだけで利用できる新機能として導入したわけではない。

生成モデルはFFT-periodicな帯域制限Gaussian、区間中央の天空共分散、一定の局gain/LO、正確なsample clock/decoder scaleを仮定する。保たれるRF channel中心は8中3であり、全2.048MHzがそのまま画像の有効帯域になるわけではない。Cas A参照は既存の形状代理で、flux/SEFDは実測ではない。

既存templateの観測側noise.enabledはFalseでもproducerはSEFD雑音を作る。新workflowはraw自体を変えずmetadataをTrueへ明示しschemaを確認した。観測側config.seed=42はtemplateのschema値で実生成seedではない。実seedと真値rateはinput外のgeneration記録へ保存した。既存producerはgainの真値ベクトルを返さないので、その値を保存したと主張しない。SEFD仮定と正確なclock/scaleは与えており、未知SEFDや時計まで解いたものではない。

| 原本 | 実生成seed | 仮定SEFD Jy | VDIF byte | worker秒 source / installed | peak RSS GiB source / installed |
| --- | ---: | ---: | ---: | ---: | ---: |
| high_a | 131001 | 1000 | 100003840 | 8.13 / 8.88 | 2.517 / 2.518 |
| high_b | 131002 | 1000 | 100003840 | 8.63 / 9.11 | 2.518 / 2.518 |
| weak_a | 131003 | 10000 | 100003840 | 9.26 / 8.77 | 2.517 / 2.518 |
| weak_b | 131004 | 10000 | 100003840 | 8.57 / 8.96 | 2.517 / 2.518 |

各workerは別processで順番に実行し、空きdisk4GiB、MemAvailable8GiB以上を要求した。VDIFは1frame8224byte、原本1件100003840byte、4件400015360byte。metadataを含む512MiB/環境、両環境1GiBの上限内だった。最大worker RSSは約2.518 GiB。これは生成/構造検査の有限測定で、相関・画像化の最低PC仕様や全夜/GPUの性能ではない。

## 4. 検証条件・結果

### 原本の構造と再現

全8局×1520frame×4原本＝48640 headerを各環境でBasebandから読み、秒・frame番号・ref epoch・局ID・EDV0・8bit complex・frame長・invalid flagを確認した。各局の先頭/末尾計64frameを復号し、sample位置・scale・ADC単位・数値SHAを残した。全payloadをsampleごとに物理モデルへ独立照合した試験ではない。

source/導入coreで76入力fileの全byte、truth/generation/boundary archive12件、68数値配列、全科学JSONが一致した。4seedと各8局のVDIF hashベクトルは重複しなかった。同じ4条件の再現であり、独立8観測と数えない。各workerの読込module34個はsourceの正確なディレクトリまたは導入prefix内。導入側はcheckout外・runnerなし・PYTHONPATHなしで実行した。

worker既存出力への4再試行とstudy全体の再試行を拒否し、原本SHAを保持した。両環境の計測値は[measurements](../../validation/runs/stage131/measurements.json)に保存した。生成とheader検査の時間はmodule importを除き、RSSはprocess全体の高水位値を含む。

### 試験・変更範囲

新9＋既存VDIF5のsource14試験/0.90秒、導入済み14試験/1.05秒が成功。両49既存警告、除外0。seed重複、出力ID、資源不足、実VDIFの重複frame/invalid/truncationを検査した。両2252は収集のみで全2252は未実行。最新全回帰121の両2116成功（609.28/607.50秒、各27396既存警告、除外0）を引用し、科学package不変のため全回帰を繰り返していない。

初回は破損frameを作る試験で、Basebandのimmutable headerを直接変更しようとして1失敗/13成功で止まった。headerをcopyしてからframe番号を変えるように直し、正式な両14試験を再実行した。producerや数式は変更していない。sourceログにMatplotlib importの一時cache警告も残ったが、原本の数値・SHAは一致し、画像化は呼んでいない。ログ内のローカルpathはGit管理外で保持する。

凍結429file、既存core/package 215file、通常環境pip freezeは不変。既存121 wheel103fileと4assetがsource/導入先へbyte一致し、新wheel・ブラウザは実行していない。公開監査指摘0、文書リンク1716件で欠落0。

[正式記録](../../validation/runs/stage131/README.md)に固定条件・原本/境界SHA・全構造の集計・計測を保存し、大容量VDIF/真値配列/境界復号はGit管理外`outputs/stage131-source-study/`と`outputs/stage131-installed-api/study/`に置いた。

## 5. 制約・未解決事項

零天空は今回生成していない。既存producerは共分散の対角にsource1000を固定しており、同じAPIで正しいflux0を表せないためである。modelやfluxを偽装して零天空にせず、必要なら別段階で物理モデルから定義する。この4件からfalse-alarm率や未知LOの成功確率を算出しない。

区間中央の狭帯域近似と時間変化の計算上のphase上限は約0.00624/0.00192radで、実測のcoherenceや誤差区間ではない。全frameは有効で、RFI・欠損・実OCXOの変動を再現したものでもない。

実RTL-SDR/OCXOのCas A、実SEFD・FFT独立性、低SNR画像尤度、弱い実信号の未知gain/LO、全夜/GPUは未検証。Windows収録は除外を維持する。

## 6. 次段階

132で同じ固定原本を.3/1/3秒、未知LO取得graph・補正相関・Closure・画像の主経路へ渡す候補とする。pilotと最終積分が同じ原本内で共有する情報を明記し、取得停止・不足・未収束を0画像や除外にしない。真値は評価専用、既定と別の罰則を比べるなら条件を先に固定する。

残量に余裕を確保して次段階を選び、140の文書整理・150の根本見直し・2026-11-06 15時の期限を維持する。
