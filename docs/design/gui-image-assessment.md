# 保存済み画像結果のGUI評価

段階121は[段階109の判定API](../reports/109-image-path-acceptance.md)をGUIへ接続する。画像を作り直す処理ではない。

`GET /api/jobs/<実行ID>`は、`rml`・`analysis`・`sequence`・`synthesis`にだけ`image_assessment`を付ける。`GET /api/jobs/<実行ID>/image-assessment`から同じ評価をJSON添付ファイルとして保存できる。その他の種類と存在しないIDの評価保存は404。元の`summary.json`は変更しない。

| 項目 | 意味 |
| --- | --- |
| `schema_version` / `type` | 1 / `gui_image_assessment` |
| `job_state` | 保存した処理状態。待機・中断も残す |
| `source_summary_sha256` | 読み取ったsummary原本bytesのSHA256。原本なしはnull |
| `state` | `available`または`invalid_record` |
| `reason_code` | 不正状態・不正summary・完了記録の矛盾・不正RMLの区別 |
| `assessment` | 既存109の`assess_rml_result`の返り値。不正記録はnull |
| `reference_note` | 参照なし・v2評価・旧参照・不正参照の区別 |

`queued`は109評価では`running`、`interrupted`は`incomplete`へ対応し、元の`job_state`を併記する。RML未実行は`not_run`、選択された探索の`optimizer_success`が偽なら`not_converged`。有効なRMLと古い参照値が同居する場合は、数値収束を表示しつつ参照差を未評価にする。参照値がないことを誤差0へ置き換えない。

形状差はcomparison_versionが整数2の全支持領域による参照比較だけを採用する。画面の`NRMSE`は比率である。GUIは合格閾値を新設せず、参照なしに画質を採点しない。`actual_observation_success_certified`と`low_snr_likelihood_validated`は偽のままである。

評価は保存した記録の診断であり、画像ファイルの現存や入力の真正性を認証しない。不正記録の扱いはJSONとして読めた構造が対象で、構文の壊れたJSON全体を修復する機能は含まない。評価へ原本pathや生の例外文は転記しない。元summaryそのものの配布・匿名化は別途必要である。

正式な表示・保存・実workerの確認範囲は[段階121](../reports/121-image-assessment-gui.md)を参照する。
