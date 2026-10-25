# 同じrateを使う最終積分と画像の検証

段階113の開発用workflow。112で取得した各seedの3秒pilotのrate-only profileを固定し、同じ原本・clock・scaleを最終積分0.3/1/3秒で処理する。局rateの再推定やSNR閾値の変更は行わない。

```bash
python tools/run.py workflows.integration_image_validation \
  --reference outputs/stage112-source-study \
  --seed109-truth outputs/stage112-preliminary/truth-relative.npy \
  --output outputs/integration-image-new
```

既存 `correlate_aligned`、`image_closure`、[画像評価API](image-assessment.md)を使う。RMLは32画素・16秒角、SNR10、FWHM240秒角Gaussian prior、starts1、max_iterations2000、seed21を固定する。Closure不足の規定ValueErrorだけを未画像化として保持し、未収束画像も捨てない。

真値は観測設定のcopyへ生成model/fluxを戻して事後再構成し、保存した生成truthと配列完全一致を確認する。観測設定と推定器はunknownのまま。真値を事前画像・初期値・周波数推定へ渡さない。

出力は各条件の全相関配列SHA、Closure全有効数、RML summary、[完了・収束・参照適合の評価](image-assessment.md)、全support比較version2、保存画像SHAを含む。導入版の既存相関/RML CLIと、全数値配列・全科学JSON・画像差を照合する。経過秒と入力archive SHAは各実行の来歴として保持し、科学値の一致から分ける。

データを使わない同じGaussian priorも、同じunit flux・110秒角共通beam・平行移動・全supportで評価する。priorより画像差が小さいかを記録するが、良くなった一例だけを科学的成功認定にはしない。[段階113](../docs/reports/113-integration-and-image.md)を参照。

workflowの作業用summaryにはnative CLIへ渡す絶対pathがある。公開記録は原本・profile・manifestの場所をリポジトリ相対へ一般化し、SHAを残す。推定用入力と評価用truthを混ぜない。
