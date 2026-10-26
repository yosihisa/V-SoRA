# 段階128の正式記録

[レポート](../../../docs/reports/128-regularizer-image-controls.md)の固定罰則成分比較を記録する。

- [reference.json](reference.json)：新9fit/27探索/81残差評価、own設定の目的関数分解、初期reference SHA・入力6SHA・画像SHA。baseline127の3fitは引用で新しくfitしていない。
- [regularizer-controls.png](regularizer-controls.png)：同じ生成データでの学習/未使用D。星印は選択run未収束。左右の色scaleは違う。結果から既定値を選んでいない。
- [images.npz](images.npz)：truth8/embedded_truthと9つのpreset__split相対画像。生成truthは仮定flux、fitは総和1。
- [cell-residuals.npz](cell-residuals.npz)：9case×3支持（training/unused/all）×3画像（fit/prior/oracle8）×8時刻×8channel。valid=false/count0/NaNを0点にしない。
- [verification.json](verification.json)：両93対象、導入CLI9/54配列/初期reference9byte/全JSON/9FITS数値WCSchecksum/37moduleprefix/非上書き、package不変。全2243は収集のみ、最新全回帰121両2116を引用。

Git管理外`outputs/stage128-source-study/`に全fit・詳細セルJSON・初期reference、`outputs/stage128-installed-api/`に独立導入CLI9件と照合を保存した。元入力は127のcontrol/truth8/embedded truthと3training.npzの6SHAへ照合し再生成していない。`outputs/stage128-preparation/`に目的/固定条件/進捗/凍結SHA/対象試験/collectを保存した。

初期referenceは不変のconstructor priorと初期化の式・seedから計算して係数間の一致を確認したもので、optimizer呼出を捕捉したtraceではない。truthと未使用データでrunやhyperparameterを選んでいない。3つの係数を変えるとFの尺度や相対停止基準の働きも変わり、数学的な大域最適解だけの比較ではない。今回既知の数値零失敗は0件で、全9fitが画像を返した。未収束2件を除外していない。
