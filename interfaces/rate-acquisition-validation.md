# 同じ長いVDIFでpilot取得を比較する検証

段階112の開発用workflow。productionの推定・相関・Closureを変更せず、固定seed109/110/111とpilot1/2/3秒の全9条件を実行する。

```bash
python tools/run.py workflows.rate_acquisition_validation \
  --output outputs/rate-acquisition-new --seed109-input outputs/stage112-preliminary
```

`seed109-input` は既存の3.04秒予備原本と生成条件の保存先。原本の全SHAを確認してコピーし、正式な相関は全て新しい出力へ再実行する。110/111の原本も同じ固定仕様で生成する。予備の診断結果は合格へ流用しない。

各seedで同じ3.04秒原本を使う。sample数が変わると乱数消費やgain/LOが変わるため、以前の短い109原本との違いをpilot長だけの効果とはしない。seed数3から一般的な検出率を推定する目的でもない。

`science` は処理状態、完了工程、全基線graph、率推定の科学項目、SNR10でのClosure有効数、全相関配列のdtype/shape/byte SHA、科学metadataを保存する。配列は導入版と直接値も照合する。絶対出力パスや場所に依存するarchive/profileの来歴SHAは各処理が別に保存し、科学値の一致とは分ける。archive全体のbyte一致を要求した規約ではない。

`maximum_station_rate_error_hz` は生成した真値を事後比較に使う。推定器へは渡さない。`calculated_minimum_constant_rate_boxcar_retention` は一定残留rateを仮定した `abs(sinc(delta_rate_baseline * 0.3s))` の全基線最小値で、測ったcoherenceや将来の画像保証ではない。

規定のgraph切断・基線差不整合は未完了条件として保存する。未知の例外は停止する。未完了時のClosureや配列はnull、相関できたがSNR閾値を通るClosureがない場合は測定した0となる。新しいRML画像は作らない。[段階112](../docs/reports/112-long-pilot-acquisition.md)を参照。
