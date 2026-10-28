# 段階138の時計入力契約

- [全科学記録](reference.json)：修正前4条件、weights変化、修正後4原本の全数値識別/metadata/入力identity。原本は131固定、再生成なし。
- [正式検証](verification.json)：新44＋対象75、両全2321、wheel103＋4assets、native API/CLI、両実GUI、原本保持・監査。
- [有限実行記録](measurements.json)：対象/全回帰/4ms相関/GUIのwall timeと出力容量。CPU単体時間や全夜/GPUのbenchmarkではない。

sourceはtools/run.py workflows.clock_input_contract_validation、導入側はtools/verify_clock_input_contract_installed.pyをcheckout外から絶対指定して再現する。raw-referenceは131source-study、record131は公開131/reference.json、old-referenceはGit外の138-before-reproduction/reference.json。wrapperはcheckoutを必要とするが、製品は導入prefixから読む。既存出力は上書きしない。

実入力の情報整理はinterfaces/linux-input-readiness.md、clock型規約はinterfaces/clock-model.mdを参照する。正しい数値の入力契約を満たしても、物理的な時計精度や実受信機を確認したことにはならない。
