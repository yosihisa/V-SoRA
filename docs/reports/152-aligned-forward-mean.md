# 段階152：実整列APIの幾何・RF/rate位相と、保存平均を照合する

- 作成日：2026-10-29
- 状態：完了（決定論的な有限参照。製品変更・実機較正なし）
- 比較元コミット：3255b8112f71d5b490dc7ae94df4ff59a1f918ab（151）

## 読者向け概要

相関器は、sampleを補間して時刻を揃え、幾何遅延と周波数差の位相を掛け、FFTと局間の積からvisibilityを保存する。146では補間等の係数を確認したが、RF/rate位相と保存までを主比較へ含めていなかった。

今回は実`correlate_aligned`を使い、既知の六つの電圧probeを通した。補正後の電圧、全8チャネル・3基線のvisibility、局powerと、六probeの平均が独立係数計算へ一致した。readerだけは合成decoded frameへ差し替えたため、実VDIFのdecode・量子化・実受信の確認ではない。画像側の点画素Fourier平均との一致や、雑音共分散の校正も今回の結果には含めない。

## 1. 目的・対象範囲と完了条件

009/014の既存整列試験には、強い連続波を実VDIFへ保存してsample時計/RFを補正する確認がある。049は固定kernel、055/059/061/078は時間依存や三次統計、146は実SampleBufferの時変query/FIR/補間/FXを扱う。今回はこれらを再実装せず、**実整列APIのRF/rate位相から保存された全チャネル平均まで**の未接続差を選んだ。

既存146の独立Kaiser/FIR tap計算を再利用し、独立なquery線形補間・sinc・DFT・位相の係数を合成する。実APIの補正電圧・保存vis/power・probe平均をRTOL1e-9/ATOL1e-10で照合する。RF位相省略とrate符号反転の負対照には、規格化平均差1e-4超を実行前に固定した。

製品API・尤度・係数は変更しない。新workflowだけを追加し、関連既存targetをsource/導入の両環境で実行する。全科学summary/数値配列/保存NPZの一致、正確module位置、非上書き、原本76SHA、既存451項目とpackage byte保持、レポート/索引/計画/小容量記録・公開までを完了条件とした。各study worker120秒、追加64MiB、公開512KiB以下。MC0、seed/MCSE対象外を固定した。

## 2. 固定入力と、実行した部分

| 項目 | 固定した条件 |
| --- | --- |
| 局・sample | 3局、各512 complex sample、Fs2048000、実rate＝公称rate、offset0 |
| 相関 | FFT8×16block＝128sample、start96/Fs、span62.5µs、1積分 |
| 幾何 | 131 high_a設定の先頭3局とUTC/RF1.42GHz/phase center。実geometry_at_timesで端点・中点・中心を評価 |
| 供給rate | なし（0,0,0）と既知の（0,700,-1100）Hz。推定器は使わない |
| mode | Fs×[.03125,.15625,-.21875]の3周波数、局gain [1,.8,1.1]×exp(i[0,.3,-.7]) |
| probe | 各modeの正負、計6。両rate条件で同じ電圧を共有し、各12実API/環境 |
| reader | 合成decoded64sample frame、全valid、sequential。実SampleBufferのFIR状態・guard・補間はそのまま |

manifest/clock/rate JSONの実loader/validator、実幾何、SampleBuffer、RF/rate位相、FX、spectral保存を実行した。manifestは既存3 VDIFの所在を参照するが、原本は存在検査だけで、科学入力は置換readerのメモリ電圧である。元のdecoder・量子化・header/seek検査、上位InputIdentity経路、未知clock/rate推定は主比較で実行していない。APIが返す`vdif_validation_scope`等の通常ラベルを、この差替え試験のheader検査証拠として扱わない。

観測設定のSEFD等は模擬の供給/仮定値で、このprobe生成や誤差較正に使っていない。物理的に整合した天空電圧や実観測を生成した参照ではない。

## 3. 独立計算と有限平均

実幾何の端点値はAPI側と参照側で共有する。 62.5µs内の局別delay変化は計算上0/2.26e-16/1.62e-15秒という小差であり、長い積分や一般の幾何変動を覆う条件ではない。参照側では端点からの線形式でdelayを求め、`query=(t-delay)×Fs`、65tapのsinc/FIR係数、RF/rate位相、unitary DFTを直接合成する。実補間関数・実FXを参照計算に呼ばない。幾何値そのものの独立Astropy検証や、実局位置/EOPの精度を確認した意味ではない。

3modeを列に並べた入力Aに対し、正負6probeの平均電圧は0、二次積の平均は`A A* / 3`となる。独立FFT作用素Hを掛けた各modeの局間積を、16blockと3modeで平均して期待する保存visibilityを求める。これは六つの有限入力を等重みで選ぶ明示的な平均であり、Gaussian/proper/IIDな標本やMonte Carloによる母分布の校正ではない。

実FXのconsumeを、同じ処理を実行する観測用subclassで捕捉し、補正電圧も直接係数へ照合した。保存された全チャネルのvisibilityと局power、valid FFT数16も確認した。帯域外のweightが0でもvisibilityを比較から落とさず、採用SNRやClosure/RMLは使っていない。

## 4. 結果

| 条件 | 最大補正電圧差 | 最大保存visibility差 | 六probe平均の最大差 |
| --- | ---: | ---: | ---: |
| 幾何/RF、rateなし | 2.00e-15 | 2.77e-15 | 1.11e-15 |
| 幾何/RF、供給rate | 2.04e-15 | 2.90e-15 | 1.35e-15 |

両環境とも固定許容内で、初回正式実行は成功した。負対照は独立モデル側の計算であり、誤った補正を実APIへ再投入した試験ではない。RF位相を省くと規格化平均差は約1.5173/1.5189、供給rateの符号を反転すると約0.48242で、事前閾値1e-4を超えた。rate0の符号反転は同じ0なので差0である。これらはこの既知probeの数値差で、実coherenceや振幅保持率ではない。

source/導入のsummary全JSONと19数値配列が完全一致し、さらに各12保存NPZの180フィールド（metadataを含む）を直接比較して一致した。各21製品moduleは正確なsource位置/導入prefixで、輸入moduleのbyteも一致した。導入はcheckout外cwd・runner/PYTHONPATHなし。検証helperはcheckoutの既存146等を読むが、製品moduleをsourceから導入側へ混ぜていない。workflow出力先の再使用は両環境で拒否し、既存全byteを保持した。

関連targetは両42成功、source2.99秒/installed2.30秒、各154既存警告、除外0。studyは各約1.22秒で予算内。target内には一時模擬VDIFを実decodeする既存整列試験等があるが、主比較のreader差替えと区別する。新unit/new full/collect/wheel/install/browser/画像fitは実行していない。最新の全回帰・配布・GUI基準は151の両2328成功552.61/551.31秒・各30220警告/除外0、両43対象、wheel103+4assets/両実GUI28worker/56downloadを引用し、152の新合格へ加算しない。

## 5. 変更・保持・公開

変更は`workflows/aligned_mean_validation.py`、本report/索引、計画の152完了追記、[小容量記録3件](../../validation/runs/stage152/README.md)の7ファイル。既存451コード/設定/asset、対象外tracked1479、131原本76SHA、151 wheel/package103+4assetのsource/導入全byteを保持した。製品や通常GUI151を停止・更新していない。

[全参照・summary](../../validation/runs/stage152/reference.json)、[正式記録](../../validation/runs/stage152/verification.json)に実行範囲と未実施を残す。大きい係数配列、全12出力/環境、実module path、log/scriptはGit管理外outputsに保存した。公開監査指摘0、文書リンク2062件で欠落0。

## 6. 制約と次段階

今回確認したのは、固定の幾何モデルと供給補正を使う、合成decoded電圧の有限平均の接続である。実131の8局/4ms/1024blockや0.3〜3秒、実VDIF/ADC量子化、実時計/未知LO/gain/SEFD/beam/RFI、一般の画像前方平均、雑音共分散/実効M/coverage、低SNR画像尤度、実Cas A、全夜/GPUは未検証である。145の八条件がすべて成立したとはせず、新RML/画像/GUI接続を保留する。

次153候補は、既存004/006/061等とcodec/scale/clip検証を先にreviewし、量子化前後の未接続差がある場合だけ一点を選ぶ。152の幾何/RF平均を再実行して番号を埋めず、未知推定・観測SNR選別を同時に変えない。150の根本レビューは完了、次の文書整理160/予定の専用根本レビュー200。期限2026-11-06 15:00JSTと追加reset禁止を維持する。
