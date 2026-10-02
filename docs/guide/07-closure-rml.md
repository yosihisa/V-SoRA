# 短積分からClosure＋RMLで形状を復元する

## 何を入力し、何が出るか

局の未知の利得が一時刻・一channel内では一定なら、Closureはその利得を打ち消します。入力はsample・幾何delay・LO差を補正した複素相関値と雑音重みです。ADC²のままでも使えます。画像の総相対fluxを1に固定するため、絶対Jyへの較正ではありません。

出力の`relative-model.fits`はBUNIT=`1/pixel`、FLUXREF=`ARBITRARY`、POSREF=`ASSUMED`です。座標ヘッダーは入力の位相中心を表示の基準として使う約束で、測定した絶対位置ではありません。summaryには画像の重心も記録します。

## RMLが選ぶ画像

RMLはClosureに合う画像を探しつつ、非負・滑らかさ・一般的なGaussian形状への近さを条件にします。この条件が正則化です。現在の参照実装では次を設定できます。

| 設定 | 意味 | 比較の方法 |
| --- | --- | --- |
| prior FWHM | 初期Gaussianとentropyの基準画像の幅 | 160/240/320秒角などを変える |
| entropy | 事前画像から極端に離れることへの抑制 | 小さくすると観測への適合を優先 |
| TSV | 隣の画素との急な変化への抑制 | 大きすぎると細かい構造を消す |
| starts | 異なる初期画像の数 | 目的関数と形状が一致するかを見る |
| max iterations | 最終探索の反復上限 | 上限到達と停止条件到達を区別する |

位相が一周する周期性を使う初期探索の後、独立Closureと全共分散を使うGaussian評価で探索します。低SNR分布やphaseの枝の境界を厳密に扱うものではありません。**最適化が止まったこと、Closureに合ったこと、真の画像が復元できたことはそれぞれ別に確認します。**

## コマンドとGUI

```bash
python tools/run.py workflows.closure_rml_validation --model casa --noise --integration-s 0.3 --output outputs/casa-closure
python tools/run.py vsora_imaging.rml --input outputs/casa-closure/uncalibrated.npz --output outputs/rml-another --prior-fwhm-arcsec 160 --max-iterations 2000
```

日本語GUIの「Closure＋RML」からも実行できます。観測全体の時間、一回の積分、短積分の個数を区別してください。例えば4時間に16個の0.3秒露光を分散すると、使用露光は一局4.8秒です。4時間連続収録の感度ではありません。

現在の模擬実験はvisibilityを直接生成します。LOとsample時計は補正済み、SEFDは仮定、局利得は各短露光中一定、一RF channelです。IQ/VDIFをこのRMLへつなぐ処理と、モデルを必要としないLO差推定は次段階です。

## 結果を読む

- Closure χ²/測定数：データへの適合の目安。画像を探索した自由度やSNRによる選別を補正した統計的p値ではありません。
- 位置合わせ前のNRMSE：表示原点も含む誤差。
- 位置合わせ後のNRMSE：同じ110秒角のGaussianで比較し、平行移動だけを合わせた形状誤差。移動量も保存します。模擬の真値を比較段階でだけ使います。
- 相対flux総量1：測定結果ではなくClosureの情報不足を補う基準です。
- 初期値ごとの目的関数：局所解を調べる材料。低いχ²だけで形状の正しさを保証しません。

段階021のCas A仮定条件では、0.3秒×16露光で形状誤差34.2%、3秒×16露光で8.7%でした。生成画像を事前画像に使っていません。3秒では乱数seed・事前幅の変更でも5〜9%でしたが、2000回の反復上限に達した探索が残ります。この有限実験だけで実観測を保証しません。[条件と結果](../reports/021-closure-rml-reference.md)、[設計と出典](../design/closure-rml-plan.md)を参照してください。

## skyモデルを要求しない周波数差推定

短いpilot内では、各基線・各channelの複素値は未知の定数として扱い、時間方向の位相回転だけを探せます。段階022でこの参照処理を追加しました。局gainと天体の絶対flux/位相を与える必要はありません。sample時計は先に整列する必要があります。GUIの「動作検証」からIQ補正後のClosure回復を確認できます。[適用条件](../reports/022-model-free-rate.md)を参照してください。

## VDIFを指定して解析する

日本語GUIの「VDIF解析」で、WSL上のsession manifestとsample時計モデルを指定できます。既知fluxを要求せず、source.model=unknownの設定を使えます。原本→sample/幾何整列→短pilot rate→IQ再相関→Closure→相対RMLを5工程で実行します。

現在は600m・1秒以内の短区間、一回の画像積分です。長時間Cas A合成と3秒整列は後続段階。pilotの有効時間内に画像積分が収まること、FIR/補間用の前後guardがあることが必要です。[入力・出力・失敗の規約](../../interfaces/closure-pipeline.md)を参照してください。
