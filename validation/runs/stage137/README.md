# 段階137の既存GUI検証

- [全caseとdownload SHA](reference.json)：24pilot＋3一セル雑音＋1時間数不足、全28診断・28summary。科学値は公開135/136へ全field照合した。
- [正式検証](verification.json)：両実Chromium、672行、50null/174負/148の1超、対象試験・module・原本/旧package不変・公開監査。
- [有限実行記録](measurements.json)：所有した試験/browserの秒数と出力量。全夜/GPU/最小PCの性能ではない。
- [390px表示](mobile-result.png)：弱い条件の推定rate回転。無制限power比と未判定をそのまま表示する。

再現にはtools/verify_saved_diagnostics_browser.py --repository checkout --output 新出力 --mode sourceまたはinstalledを用いる。PLAYWRIGHT_BROWSERS_PATHは導入済みChromiumの保存先を指定する。helperはcheckout依存だがinstalled server/workerはcheckout外・runner/PYTHONPATHなし。既存GUIを変更せず、通常GUI8765と異なる所有portを使う。

入力は132studyの保存原本、期待値は135/136公開記録。全科学JSONと表示数値の照合は、実機のnoiseモデルやcoherence、confidenceの校正ではない。
