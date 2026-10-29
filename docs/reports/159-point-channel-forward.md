# 段階159：供給点形状の空間位相と有限FFTチャネル平均

- 作成日：2026-10-29
- 状態：完了（固定幾何・単一toneの条件付き参照）
- 比較元コミット：ccecb581b99e0f33753764e6ae5628353d2e783f（158）

## 読者向け概要

画像のFourierモデルは、ある周波数の波が局の位置に応じて持つ位相を計算します。一方、短いFFTの一つのチャネルには、中心周波数と違う波も漏れ込むことがあります。漏れ込んだ波の空間位相は、漏れ先のチャネル中心ではなく、元の波の周波数に従います。

今回は、この違いを固定点形状と単一toneだけに限定し、実整列APIのFIR・補間・RF位相補正・FX・保存まで照合しました。**実観測の前方モデルや低SNR画像尤度を完成した段階ではありません。** 定常toneの有限参照で、広帯域の天空や実機へ適用する補正係数を求めていません。

## 1. 目的・対象範囲

009/014の連続波時計/幾何、055/059/061/078の既知Gaussian/時間共分散/FFT追加統計、128/129の無雑音・保存相関画像、152の任意3mode平均と、現在の生成/geometry/synthesis/RML/FX・関連試験・validationをreviewしました。既存の点源生成・画像側Fourierを再実装せず、toneの空間位相と有限チャネル応答の未接続差だけを選びました。

変更は新[検証workflow](../../workflows/point_channel_validation.py)、本レポート/索引/roadmap/[小容量記録](../../validation/runs/stage159/README.md)。製品/尤度/RML/weight/GUIの変更なし。原本131high_aの観測/manifestをSHA固定して借り、最初の3VDIFは所在検査だけでpayload不使用。新しい検証用metadataと6保存相関を作り、原本131の再相関/再生成をしていません。

## 2. 完了条件・実行範囲

3局/512sample、Fs2.048MHz、FFT8×16block、start96/Fs、span62.5µs。供給station UVWはm単位で次の値へ固定しました。

```text
[0,0,0], [120,35,80], [-90,170,-60]
delay_s = w / 299792458
```

`geometry_at_times`をこの一定UVW/遅延へ置換し、readerも合成decoded64sample frame・全valid・seekFalseへ置換。**実Astropy/EOP/地理ENU→UVW、codec/量子化/header/seek、上位InputIdentity、未知clock/LO推定は主比較で実行していません。** 実manifest/時計JSON検査、SampleBufferのFIR状態/guard/補間、RF補正、FX/saveは通しました。実APIが通常返すVDIF scopeやgeometryの説明文は、この差替え試験で実headerや地理精度を確認した証拠にはしません。

時計はactual=nominal/offset0、rate0、局gain1、受信機雑音なし、電圧振幅1ADCを供給。元の仮定SEFDを処理で使わず、source.model unknownという設定を実観測証拠にもしていません。SK/RFI採否を一度に変えないため、新manifestのspectral_qualityを外し、既存RF guardのweight0を残したまま全チャネルvisを比較しました。

解析用の8×8/64arcsecの点形状を、center(4,4)とoff-axis(1,6)へ固定。記録用観測configの元32×32/16arcsecとは別の明示的な解析格子です。tone f/Fsは0、.125、.15625。6条件は決定論的入力で、Gaussian/IID/MC標本ではなく、seed/MCSE対象外です。

## 3. 独立な式と実APIの照合

点の方向を `d=[l,m,sqrt(1-l²-m²)-1]`、各局の付加遅延を `Delta_s=UVW_s dot d/c` とします。供給波形は

```text
raw_s[n] = exp(2πi f n/Fs) * exp(2πi (RF+f)(delay_s+Delta_s))
```

です。既存146のI0 Kaiser/sinc係数式を独立な定常tone応答A_s(f)へ展開しました。有限DFTの漏れpower K_k(f)はFFTを呼ばない8項の直接和で計算し、全チャネルsum8、on-binの主K=8を確認。単位的FFTの正規化に由来する値で、独立標本数・実帯域・flux較正ではありません。

補正後電圧と保存cross-powerの参照は、

```text
電圧_s(t) = A_s exp(2πi f t) exp(2πi (RF+f)Delta_s)
V_k,ij = A_i conj(A_j) K_k exp(-2πi (RF+f)(Delta_j-Delta_i))
```

です。全channel/3基線/6条件を固定RTOL1e−9/ATOL1e−10へ照合しました。保存uvw(f_k)に対する既存`direct_visibility`と実RML constructorのFourier行列も、独立point和へRTOL1e−11/ATOL1e−12で照合。RML constructorは実保存weights/SNR10の基底を構成しましたが、目的値・gradient・fitを評価していません。支持が得られたことを、近似誤差や尤度の校正と扱いません。

unit-sum点形状はnormalizedな空間位相参照で、保存相関はADC²です。既存APIの慣用的なflux表現を、実Jy/SEFD較正へ読み替えていません。truthは波形生成と独立検証だけに使い、未知量の推定・係数調整へ渡していません。

## 4. 結果と正式検証

全6実API条件が一致。最大補正電圧差4.80e−13、visibility差3.68e−12、RML point行列差2.67e−15以下でした。各16 FFT block、読取りは各局5個の合成decoded frameであり、実VDIF frameの新decode数ではありません。

off-axis、f=.15625Fsのtoneが+Fs/8チャネルへ漏れる条件で、**空間位相だけ**を中心RF+.125Fsへ置換した負対照は相対差約.0002603865となり、固定閾値1e−6を超えました。他の応答/正規化は同じです。これはチャネル中心の画像Fourierを単一漏れtoneへそのまま当てると同一にならないという計算参照であり、RMLの不具合再現、131/133画像差の単一原因、実機誤差率ではありません。

初回source対象成功後、検証workflowが解析用8pixelsを観測設定にも入れたため、既存schemaの最小16pixels検査でAPI開始前に停止しました。全worker終了後、新workflowのその上書き1行だけを除き元の記録profile32×32/16arcsecを保持。別の解析用8×8点形状・raw/tone/幾何/許容/負対照は不変で、source+installedの全選択を再実行しました。初回log/部分入力/凍結を保存し、初回成功を正式件数へ合算していません。

最終source**11成功/1.13秒**、installed**11成功/.71秒**、両警告0・除外0。新unitなし。全科学JSON/[38配列](../../validation/runs/stage159/arrays.npz)、各6保存NPZの60フィールド（metadata含む）が完全一致。24製品moduleの正確source/prefix/byte、native checkout外/runner/PYTHONPATHなし、非上書き2を確認しました。

旧458+newworkflow凍結459、入力metadata2/原本131の76/対象外tracked1518/引用33fileのSHA保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103+4assetsのsource/wheel/installed全byte不変です。study本体wall約.0385/.0339秒、生涯peakRSS133488640/134049792byte、保存62964/63628byte。各worker120秒/追加64MiB/公開512KiB/段階1200秒内。保存量・生涯RSS・単発wallを全夜性能へ外挿しません。公開監査指摘0、文書リンク2151件で欠落0。

[全条件・入力/一次コードSHA](../../validation/runs/stage159/reference.json)、[正式検証](../../validation/runs/stage159/verification.json)。新full/collect/wheel/install/browser/MC/VDIF生成・decode/画像fitなし。新保存相関6件は合成decoded readerによる小参照であり、原本131の再処理と区別します。最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告の引用。通常GUI151も変更していません。

## 5. 制約と次段階

平均の接続を固定幾何・単一点・toneへ限定した参照です。実際の広帯域天空では入力周波数のPSD、有限filter/channel応答、局別変化や雑音を合わせて扱う必要があります。今回のtone一致を、その周波数積分・未知局量の推定・実FFT独立性・noise共分散/coverageの成功へ合成しません。

八条件、実131の8局/4ms1024block/.3〜3秒、低SNR画像尤度、実Cas A、未知実LO/gain/SEFD、beam/RFI、全夜GPUは未校正。新RML/画像再fit/GUI/外部追加反復/truth係数調整/Windows収録は保留です。

次160は必須の文書整理として、二全体文書/計画/短い案内09/入口/索引/運用を技術基準159へ揃えます。151の製品/full/wheel/GUIと152〜159の限定参照、失敗/訂正/未実施を分けます。新しい数値計算を文書段階の成功へ足さず、実入力新回答を優先し148質問は繰り返しません。予定根本レビュー200を待たず前提が崩れれば見直します。
