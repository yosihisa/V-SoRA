# 相関ファイルから一つの時間・周波数の雑音を診断する

`vsora-noise-diagnose --input correlation/shard-00000.npz --time-index 0 --channel-index 16 --output outputs/new-noise.json`

時間・channel番号は0始まりです。例の16はFFT32の中央channelで、実際の入力の周波数配列を確認して選びます。保存を終えた独自NPZ v2を読み、JSONを新規作成します。既存出力は上書きしません。入力のSHA256も保存します。

## 必要な情報

visibilityだけでは局の自己雑音を推定できません。次の統計を、同じ正規化・局順・電圧単位で保存します。

| 配列・metadata | 役割 |
| --- | --- |
| `visibilities[T,F,B]`、`pairs[B,2]` | 各基線の複素相関と局番号 |
| `diagnostic_station_power[T,F,N]` | 各局のpower。局共分散行列の対角 |
| `diagnostic_station_valid_fft_count[T,N]` | 局ごとの有効FFT数 |
| `valid_fft_count[T,B]` | 基線の両局に共通する有効FFT数 |
| `diagnostic_station_flags[T,F,N]`、`weights[T,F,B]` | 品質判定・無効情報 |
| `config.stations[].id`、単位のmetadata | 局の識別とpower・visibilityの単位の対応 |

2〜8局・完全基線を対象とします。選択cellの全局flagが0で、全基線の重みが正、各局と基線のFFT数が同じMで、M≥局数であることが必要です。基線の共通数も同じなら、局と基線が同じFFT集合を使用したことを確認できます。単位は相関とpowerの両方がADC²または両方がJyです。

段階047以降の整列相関器は基線FFT数を追加保存します。既存v2の数値配列の意味は変わりません。FFT数のない旧ファイルや、情報を保持していない合成ファイルから数を推測しません。

## 結果の読み方

- `inactive`：選択cellに正の基線重みがない。
- `unverified`：情報不足・単位差・flag・部分基線・FFT集合差などがあり、この推定を適用できない。`reason`を確認する。
- `conditional_estimate`：必要な保存情報が揃った。**独立・平均0・proper Gaussian電圧・時間中に一定の局共分散という仮定を置いた計算**で、実機でその仮定が成立したという意味ではない。

局powerを対角、visibilityを非対角に置き、[有限標本補正](sample-visibility-noise.md)から全基線のRe・Imの共分散を求めます。その後[Closureへの一次伝播](joint-closure-noise.md)を計算します。推定器へ真の天体画像や局gainは渡しません。

visibility共分散は仮定の下で多数の試行の平均が不偏ですが、測定visibilityを使ったClosureの一次伝播に不偏性や正しい信頼区間を保証しません。`closure_joint_valid=false`の行のゼロ値は、誤差ゼロの測定ではなく無効行なので除外します。

`nominal_common_fft_blocks`は矩形FFT blockの**個数**です。FIR・補間後の実際の独立標本数ではありません。`iid_fft_independence_verified`、`stationary_gaussian_model_verified`、`covariance_confidence_calibrated`はfalseです。量子化・RFI・gain変動も未校正です。現行rate/RMLの重み・採否には適用していません。

詳細な条件と模擬VDIFの検証は[段階047](../docs/reports/047-observation-noise-diagnostic.md)を参照してください。


段階048以降はJSONに`pairs`、`triangles`、`quadrangles`も保存し、局番号と行順を確認できます。相関値や共分散の数値計算法の変更ではありません。日本語GUIの操作は[GUIガイド](../docs/guide/06-gui.md)を参照してください。
