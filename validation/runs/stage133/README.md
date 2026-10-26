# 段階133の短積分画像記録

- [全科学結果](reference.json)：固定設定、全12条件、10画像の全run/選択・assessment・形状差・fitted/prior/truth目的分解、入力SHA。
- [計測](measurements.json)：各所有RML CLIの有限CPU秒数と出力サイズ。
- [検証](verification.json)：両87対象、全2270はcollectのみ、126数値欄＋12文字列欄、10FITS/PNG、prefix/非上書き/旧package不変。
- [比較図](comparison.png)：中央512秒角表示、全支持v2指標、共通110秒角beam。画像出力/収束/形状を分離。

入力はGit管理外outputs/stage132-source-study/の12相関、outputs/stage131-source-study/の4原本と真値。正式出力はoutputs/stage133-source-study-final/とoutputs/stage133-installed-api-final/study/。初回出力は同名末尾-final無しに保持し正式件数に加えない。実生成/再相関なし。

source実行はtools/run.py workflows.short_integration_images --reference 相関study --raw-root 原本study --reference131 公開131/reference.json --output 新出力。導入版はcheckout外からtools/verify_short_images_installed.pyを絶対指定し、同じ入力を使う。PYTHONPATH/runnerなし、検証helperはcheckoutに残る。全fit後にだけ真値を読込。個人pathを含むCLI/runtime logはGit管理外。

12条件は重複pilot/最終積分の比較で、独立12観測ではない。制約不足2件に0画像を代入せず、8未収束画像を除外しない。元原本76・相関12・真値4のSHAと元相関の数値識別を維持する。画像が返ることやoptimizer収束は実Cas A成功の認定ではない。
