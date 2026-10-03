# 段階030：画像の全成分を保持した位置合わせ評価

- 作成日：2026-10-03
- 状態：比較処理・有限再評価完了
- 比較元コミット：edca267

## 読者向け概要

Closure画像は絶対位置を決められないため、模擬の真値との比較時だけ平行移動を合わせます。従来は移動で画面外へ出た成分が誤差から消えていました。今回は広い範囲で位置を調べ、画面外の成分も保持して評価します。保存済み画像を再評価した結果、低感度条件の形状誤差は約35〜39%でした。

## 1. 目的・対象範囲

比較関数の位置探索とsupport（画像の成分が存在する全範囲）を修正。段階024/028の生成済みCas A画像と事前幅を再評価。RML再実行、雑音統計・実機画像は対象外。

## 2. 完了条件

- 既知の整数・小数移動、画面外成分保持、不正入力を検証。
- 段階024/028を同じ新定義で再比較し、旧数値を書き換えず併記。
- source/wheel回帰、配布日本語GUIの実操作、記録・公開監査・コミット。

## 3. 実際に行った作業

`registration.py`を追加。ゼロの余白を持つ画像の全整数移動区間を候補にし、各区間内でbilinear（周辺4画素の線形重み）補間の小数移動を探索。4つの整数移動画像の内積を使い、二乗誤差を安価に計算する。各区間9初期値、座標ごとの二次式の最小化、100反復上限。32画素なら各方向±31画素、3844区間。連続空間の厳密な大域最適性を証明するものではない。

`experiment.py`のcompare_relativeをcomparison_version=2へ更新。総量1にした元画像をGaussian平滑化し、その裾と全移動を覆う余白を追加。誤差は全supportのL2ノルムを真値ノルムで割る。移動後にfluxを再調整しない。返す表示画像は元の画面範囲のみで、評価範囲と区別する。移動量、探索端到達、補間の収束、flux保持割合、内積式と直接誤差の差を保存。

`test_registration.py`で11条件、`registration_validation.py`で固定画像を再評価。GUI app.jsと入門文書に全supportの意味を説明。`verify_registration_ui.py`は配布版を独立した一時作業場所で起動し、利用中のGUI履歴へ干渉せずChromiumから確認する。

## 4. 検証条件・結果

### 固定画像の再評価

段階024はSEFD1000Jy・1秒×8露光、段階028はSEFD10000Jy・3秒×8露光の仮定。8局、1.42GHz、4時間に分散した模擬VDIF。画素16秒角、比較beam110秒角、32画素、余白45画素。source真値と相関NPZ/復元画像をSHAで識別し、RMLへ真値を渡したり、画像を再最適化したりしていない。

| 保存済み画像 | 旧・画面内NRMSE | 新・全support NRMSE | 新しい移動量[y,x]秒角 |
| --- | --- | --- | --- |
| 段階024・高感度・prior240 | 2.80% | 2.36% | [37.01, -24.67] |
| 段階028・低感度・prior160 | 35.47% | 37.40% | [48.00, -47.12] |
| 段階028・低感度・prior240 | 33.99% | 35.15% | [16.00, -5.96] |
| 段階028・低感度・prior320 | 36.61% | 38.54% | [64.00, -64.00] |

全4ケースで探索の外側境界には未到達。移動後flux保持割合は1、内積式と直接計算の二乗誤差差は約2〜7×10^-19。新旧では探索範囲と誤差の定義が違うので、NRMSEの差を画像復元の改善として扱わない。低感度の形状誤差が大きいこと、元RMLの2000反復上限到達は残る。

### 処理の検証

- 既知[7,-8]画素の移動を逆方向へ回復、誤差10^-8未満。
- 解析Gaussianの[4.35,-6.2]画素移動：位置差0.015画素未満、bilinear補間による形状誤差約0.783%。初回の0.5%閾値を超えたため、有限補間の1%条件へ修正。アルゴリズムはこのassertionのために変更せず。
- 中心と画面端にある2成分：表示から成分の一部が外れても全supportのfluxを保持し、形状誤差>60%。初回の端に近い(1,1)画素では表示lossが小さかったため、端(0,0)を使い確認。
- ±2画素の指定範囲を超える真の移動は探索端到達を記録。移動禁止、非有限・負・総量0・形状不一致・不正scaleを確認。
- 独立した0.1画素刻みの全格子評価以上の適合を有限例で確認。厳密大域解の証明とは区別。
- source151成功（39.24秒）、wheel151成功（40.33秒）、3418既知deprecation warning。pip check成功。
- checkout外のinstalled moduleとGUIを確認。Chromium153、相対RML完了、comparison_version=2、日本語説明・font・画像表示、JS例外0、外部通信0、390px横溢れなし。初回harnessは折り畳み内の入力を操作できず停止し、欄を開くようharnessを修正して再確認。

```bash
python tools/run.py workflows.registration_validation --high-sensitivity-run outputs/stage024-vdif-casa-sefd1000 --low-sensitivity-run outputs/stage028-vdif-casa-3s-sefd10000 --prior-run outputs/stage028-priors --output outputs/stage030-registration
python tools/run.py pytest -q
```

[全評価・入力SHA](../../validation/runs/stage030/summary.json)、[画像比較](../../validation/runs/stage030/comparison.png)、[配布GUI実操作](../../validation/runs/stage030/browser.json)、[GUI画面](../../validation/runs/stage030/gui-screen.png)、[検証とwheel識別](../../validation/runs/stage030/verification.json)。ログ/wheel/既存大容量データはGit外outputs/stage030-*と元run。

## 5. 制約・未解決事項

真値がある模擬評価で、実観測の誤差率や信頼区間ではない。translationのみ、相対総量1、bilinear補間の小さな平滑化、有限の数値探索、128画素までの比較上限。画像の実際の改善・絶対位置/flux測定ではない。高感度仮定の結果を実機の感度へ置き換えない。

## 6. 次段階

長いVDIF記録から短区間を繰り返し読む処理を整備する。現在は後方の区間でも先頭からFIRを通しており、短区間の反復処理に読取・CPU費用が掛かる。必要なguardを保持した部分読取を、連続読取との数値一致とheader/time/invalid検査を含めて検証する。
