# 画像経路の評価記録

段階109。既存のpipeline/RML JSONを読み、処理完了、選択された最適化の収束、Closureの独立制約数、参照画像との差を別々に記録する。推定器、画像尤度、既存のpipeline `state` の意味は変えない。

## API

```python
from vsora_imaging.assessment import assess_pipeline_result, assess_rml_result
assessment = assess_pipeline_result(pipeline_summary, reference_metrics=None,
                                    max_registered_nrmse=None)
```

`assess_rml_result` はRML summaryまたはNoneを受け、別引数 `processing_state` を指定できる。pipeline版は明示的な `state` と重複のない `completed_steps` を必要とする。`complete/incomplete/failed/cancelled/running` を受理する。RMLが存在する場合、不正なsummaryを「画像なし」へ置き換えず例外を返す。

参照比較は任意で、[比較version2](../docs/reports/030-full-support-registration.md)の `registered_nrmse`、共通beam、全supportのflux保持率、探索境界の情報を必要とする。真値を持たない実観測では未評価のまま扱う。NRMSEの閾値を明示したときだけ、その閾値との大小を返す。閾値があっても参照画像がなければ判定値はnullである。

## 出力 schema_version 1

| 項目 | 意味 |
| --- | --- |
| `processing_state` | 呼出元が記録した処理状態。画像品質とは別 |
| `image_computed` | RML summaryが供給されたか。保存画像のbyteをこのAPIが検査したという意味ではない |
| `numerical` | 選択startの `optimizer_success` に対応する収束状態。別startの成功で置き換えない |
| `independent_constraints` | phase/logampと合計。未画像化ではnullであり、測定した0とは違う |
| `extracted_closures` | pipelineから供給された全有効Closure数。独立な制約数とは別 |
| `reference_fidelity` | 真値がある場合の比較。未評価と閾値超過を区別 |
| `recorded_issues` | 未完了、未収束、片方の制約なし、宣言した誤差超過、境界・flux保持の注意点 |

phase-onlyは振幅形状の情報を制限するが、あらゆる条件の画像化が不可能という判定はしない。最適化の収束も大域最適解や物理的な正解の保証ではない。実機成功と低SNR尤度の検証済みフラグは常にfalseで、この診断APIから自動的に認定しない。

## CLIと再現ベンチ

```bash
python -m vsora_imaging.assessment --input pipeline.json --output assessment.json
# 模擬真値がある場合にだけ追加
python -m vsora_imaging.assessment --input pipeline.json --output assessment-with-reference.json \
  --reference-metrics reference-metrics.json --max-registered-nrmse 0.1
# 開発checkoutの固定4条件ベンチ
python tools/run.py workflows.image_path_acceptance_validation --output outputs/image-path
```

CLIは入力を検証してから、新規JSONファイルへ排他的に書く。固定ベンチはSEFD1000/10000 Jyと積分0.3/1秒、同じSEFDでは同じVDIFを再利用する。未知LO推定と画像化へ真値を供給せず、比較だけで真値を使う。規定の率推定graph切断と高SNR Closure不足だけを未画像化として保存し、未知の例外は伝播させる。[段階109](../docs/reports/109-image-path-acceptance.md)が条件・失敗・限界を説明する。
