# 段階165の検証案内

[レポート](../../../docs/reports/165-public-iq-vdif-time.md)と[取得配置・実行手順](../../../docs/guide/public-voltage-data.md)を参照。

原本・提供metadata・変換VDIF・科学summary・数値配列は全てGit管理外。このディレクトリには方法と合否の文章だけを保存する。sourceは `tools/run.py workflows.public_vdif_validation`、installedは既存wheel環境でcheckout外cwd/PYTHONPATHなし、workflowを絶対pathで指定する。既存の二helperはcheckoutに必要である。

実行前固定は `outputs/stage165-preparation/purpose-fixed.md`、`input-files.json`、`frozen.json`。全400万sampleを4000sample/frameで保存し、供給20 MHz・小数秒epochを保持する。事前scale9088 ADCでの独立量子化式・全payload/header・製品iterator/range読込・native writer小数秒拒否を照合。原本からの非可逆誤差を、sample順と供給時刻の保持と区別する。

初回のsource-root検査不備は全worker終了後に修正。`attempt1/` のログ・凍結・runnerと、`outputs/stage165-attempt1-{source,installed}-study/` を保持。全選択再実行の最終は `outputs/stage165-{source,installed}-study/`、両5対象/各41既存警告/除外0、科学JSON/3配列/VDIF全byte一致、上書き拒否2。初回成功を合算しない。原本・科学workflowは不変。

詳細な `workers.json`、`targeted-*.log`、`study-*.log`、`verification-private.json`、環境計測は `outputs/stage165-preparation/` と最終studyへ保存し、公開cloneに含めない。単局/基線0、MCSE対象外、相関・Closure・画像復元・実時計較正は未検証。
