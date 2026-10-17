# 保存したwindow列の条件付き対称性

## 入力と操作

raw profile version2のraw-bispectrum.npzと対応する元相関shard-00000.npzを指定する。全時刻1〜12、全三角形1〜56、事前指定した一つのRF channelを使う。保存値・SHA・軸・局・単位の検査は既存の読込規約に従う。

~~~bash
vsora-window-symmetry \
  --input raw-bispectrum.npz \
  --source-visibility shard-00000.npz \
  --channel-index 10 \
  --output window-symmetry.json
~~~

Python APIはvsora_correlator.bispectrum_window_symmetryのwindow_symmetry_from_bispectrum（配列・原本未照合）とinspect_bispectrum_window_file（原本照合付きファイル入出力）。JSONは新規作成し、既存結果を上書きしない。段階093はAPI/CLIを対象とした。段階094から日本語GUIの「保存三次統計」で同じ検定を実行できる。時刻を絞らず全保存区間を使い、version1・13区間以上では実行ボタンを無効にする。計算不能・品質除外はworkerで停止し、自動で間引かない。

## 判定量と成立条件

各windowの全三角形について、共通電力で割ったU₃の虚部を一つのベクトルとする。[段階086](../docs/reports/086-window-sign-symmetry.md)の検定へ渡し、windowの行全体の符号を反転する全2^Q通りを列挙する。三角形を独立な標本として反転しない。検定量はベクトル平均の二乗ノルムである。

p値に統計的な意味を与えるには、選別を含む結合分布が各windowの独立な符号反転に対して不変である必要がある。各windowの周辺分布が対称という条件だけでは足りない。正しい原本SHAや異なる時刻だけで、独立性・結合対称性・局gain一定・LO補正を証明したとは扱わない。これらは出力上も未確認とする。

v1・M<3・0電力・既存品質で除外されたセルがあれば停止し、自動で間引いたり0を入れたりしない。この拒否方針だけで、上流の品質選別が対称性を保つことを保証するわけではない。channelを結果のp値で選ぶ場合の多重比較にも対応していない。入力channelと対象原本を先に定める。

Q=2の最小pは0.5で、5%の判定には分解能が足りない。Q=8は最小2/256となるが、同じwindowの複製でQを増やしてはいけない。[段階087の反例と仮定](../docs/reports/087-casa-window-symmetry.md)を参照。

## 出力と解釈

全feature、時刻、局・三角形、共通FFT数、channel/RF、符号反転の全結果を要約したconditional_test、入力SHA、仮定と未確認flagを保存する。数値を計算できること、原本照合が正しいこと、p値の前提が成立することは別々に読む。

棄却はCas Aの検出、拡がりの証明、画像の信頼度を意味しない。非棄却も点源・対称な天空・十分な感度の証明ではない。実機、時間変動LO、低SNR画像尤度へ未適用で、現在のRMLは変わらない。
