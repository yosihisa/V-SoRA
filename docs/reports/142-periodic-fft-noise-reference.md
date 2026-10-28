# 段階142：有限周期の帯域制限入力とFFT全雑音の条件付き参照

- 作成日：2026-10-29
- 状態：完了（既知・固定モデルの有限検証。131の実出力や実機の誤差校正ではない）
- 比較元コミット：e160915bd598baa92a44b501358ab4f4da3cf65e（141）

## 読者向け概要

131の模擬電圧は、長い白色GaussianをFFTし、帯域外を0にして逆FFTした有限周期の信号である。141の短い入力FIRとは相関の作り方が異なる。今回はこの周期と帯域端の規格化を、小さい既知モデルで分けて調べた。

小周期の直接電圧と、入力相関の式・周波数mode・Gaussian二次形式の計算が一致した。131と同じ長い周期の数値も式へ代入したが、131原本やその画像を再処理していない。名目FFT数を実効独立数へ置き換える機能ではない。

## 1. 目的・対象範囲

既存049/055/072/078のコードと記録を点検した。049は白色と有限固定operator、055/072/078は時間相関を持つbispectrumの母平均を既に扱う。今回は同じAPIや141の固定3tap色付けを再実装せず、131生成のsharpな有限周期bandlimitだけを最小差に選んだ。

既存aligned_fft_kernelと042 visibility_noise_momentsのIID反実仮想を再利用し、[周期FFT検証workflow](../../workflows/periodic_fft_noise_validation.py)だけを追加した。二次形式traceは既知モデル検証のhelperで、未知入力の共分散推定APIではない。製品/重み/RML/GUIは変更していない。

## 2. 完了条件

1. P512のDirichlet閉形式とFFTの入力相関、時間領域operatorと周波数mode投影の全出力共分散を照合する。
2. 実FIR・既存補間・FFTの電圧から4096試行を行い、全平均/全ReIm共分散を固定6 MCSE＋丸め許容内へ照合する。先頭2試行で全8channelの直接kernel積と実FXも照合する。
3. P6225920と無限周期の小operator計算を、MC・131原本解析と明確に区別する。
4. source/native全JSON/全配列、所属/非上書き/原本保持、関連試験、製品byte不変、文書/監査/匿名commit/pushを完了する。

## 3. モデルと独立な計算

4局の既知共分散S、FFT8・16非重複block、局offset[0,.25,.5,.75]sample、shift済みchannel3/4/5（−Fs/8/DC/＋Fs/8）を固定した。Sは共通成分1、位相[0,.4,1.1,2.2]radの成分0.7、独立受信機成分1.5で141と同じ。

131の生成はabs(f)<=Fs/4のbinを**両端を含めて**残し、active.meanの平方根で割る。周期P、K=floor(P/4)、J=2K+1とすると、規格化した入力相関は

```text
R_P(d) = (1/J) Σ_{k=-K..K} exp(2π i k d/P)
```

で、無限周期ではsinc(d/2)になる。P512ではこの閉形式をmaskのifftと照合し、全出力Cも独立な周波数modeの作用から照合した。さらにV=yᴴAyとして、E[V]=tr(AC)、複素共分散tr(ACBᴴC)、擬共分散tr(ACBC)から全Re/Im共分散を求めた。visibility自体の分布をGaussianと仮定していない。

実MCはP512/seed142/batch32/4096試行だけである。同じ電圧から3channelを取るため、独立12288観測とは数えない。131公称periodの6225920は公開131の3.04秒×2.048MS/sから確認した数値で、無限周期とともに解析式だけへ代入した。巨大なrawは生成していない。

ここは4局/16blockの小さい固定operatorである。2.048MS/sと対応させると128sample=62.5µsで、131の8局・4ms/1024blockや132の0.3/1/3秒を校正した結果ではない。geometry/LO/時変clock/ADC/VDIF/品質mask/同pilot推定は含まない。

## 4. 検証結果

### 固定モデルの計算値

| モデル | channel | 有限モデル分散 / IID反実仮想の分散 | 無限周期共分散からの最大規格化差 |
| --- | ---: | ---: | ---: |
| period512 | 3 | 1.001383873〜1.001659035 | 0.00777 |
| period512 | 4 | 1.000663587〜1.000893068 | 0.00777 |
| period512 | 5 | 1.001250996〜1.001732823 | 0.00777 |
| period131 | 3 | 1.001383873〜1.001659035 | 6.42e-07 |
| period131 | 4 | 1.000663587〜1.000893068 | 6.42e-07 |
| period131 | 5 | 1.001250996〜1.001732823 | 6.42e-07 |
| infinite | 3 | 1.001383873〜1.001659035 | 0 |
| infinite | 4 | 1.000663587〜1.000893068 | 0 |
| infinite | 5 | 1.001250996〜1.001732823 | 0 |

最右列は全Re/Im共分散の差を、無限周期モデルの行・列分散の平方根の積で割る。P512と無限周期では約0.00777、131と同じP値を使う小operator計算では約6.425e−7だった。対角比と共分散の絶対尺度の違いは別で、有限周期がどんな処理でも無視できるという結論ではない。

IID反実仮想は、同じ一blockの出力局共分散を042へ与え、時間的に独立な16FFTを仮定した比較である。観測された独立数の推定ではない。今回の約0.066〜0.173%の分散差はモデル計算値で、4096 MCから小差を精密に測定した主張ではない。単一MをRMLへ自動代入しない。

### 直接電圧と正式検証

P512の3channel全平均/全共分散要素は、事前固定6 MCSE内。平均差の最大は2.922 MCSE、共分散差は2.424 MCSEだった。MCSEは有限試行で求める平均の標準誤差で、観測confidenceやcoverageではない。先頭2試行の全8channel直接kernel積との差は最大約6.3e-15、実FXとの差は0。

source/nativeの全科学JSONと79配列を直接完全一致確認。両workerの8製品moduleを正確なsource位置/導入prefixへ確認し、nativeはcheckout外・runner/PYTHONPATHなし。検証wrapper自体はcheckoutが必要である。非上書き2件、元131の76入力SHA保持。正式数値手順は最初の実行で完了した。記録組立scriptでは数式の波括弧をf-stringの式と解釈する構文エラーが発生し、文字としてescapeして修正した。組立前の構文解析で止まったため、科学出力は変更せず数値手順も再実行していない。

既存filtered_noise/visibility_moments対象はsource52成功1.95秒、導入52成功1.40秒、両警告0/除外0。新unitなし、code/試験/tool/workflow447件を正式検証中に凍結した。workflow本体wallは3.105/3.076秒、生涯peakRSSは116.5/117.2MiB。OMP/OpenBLAS各1、各出力16MiB未満。wallはPython起動/import前を含まず、RSSはLinux RUSAGE_SELFで依存読込も含む。全夜/GPU/最低PCの評価ではない。

製品103file＋4assetは138 wheel/source/導入先と全byte一致。新full/collect/wheel/導入/browserは行っていない。[138正式記録](../../validation/runs/stage138/verification.json)の両全2321成功542.82/541.45秒・各30220警告/除外0と、両実GUI28worker/56downloadを引用する。142の新合格数へ加算せず、通常GUI8765も変更していない。

[科学概要](../../validation/runs/stage142/reference.json)、[79数値配列](../../validation/runs/stage142/arrays.npz)、[正式検証](../../validation/runs/stage142/verification.json)、[資源](../../validation/runs/stage142/measurements.json)、[再実行条件](../../validation/runs/stage142/README.md)に保存した。公開監査指摘0、文書リンク1868件で欠落0。

## 5. 制約・未解決事項

既知stationary Gaussianと固定operatorのモーメントを確認した段階である。131の実電圧/未知gain/LO・時変幾何・補間係数・量子化・flagを含む全処理の誤差校正ではない。133の全画像がpriorを改善しなかった原因を、この小さい分散差だけへ断定しない。

実FFT独立性、同pilot推定・SNR選別、未知SEFD/beam、実Cas A、低SNR画像尤度、全夜/GPUは未検証のまま。136の無制限power比をcoherenceや補正係数へ変換しない。

## 6. 次段階

143では保存pilotの推定と評価の共有条件を先にreviewし、既存の独立学習評価/相互検証と重複しない最小対照へ目的を固定する。144のSNR選別は別の未解決課題として残す。150で文書整理と専用根本レビュー。期限2026-11-06 15:00JST、追加reset禁止を維持する。
