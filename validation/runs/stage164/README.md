# 段階164の検証案内

[レポート](../../../docs/reports/164-public-single-station-iq.md)と[取得配置方法](../../../docs/guide/public-voltage-data.md)を参照。

ユーザー指示により原本、提供メタデータ、receipt、波形、スペクトル、電力配列、変換データはGit管理外に保存し、このディレクトリへコピーしない。方法と合否の文章だけを公開する。

再現は取得案内のコマンドで行う。source経路は `tools/run.py workflows.public_iq_validation`、installed経路は既存wheel導入環境のPythonでcheckout外をcwdとし、workflowの絶対pathを指定する。PYTHONPATHは使わない。原本を再生成せず、全て新しい出力先を使用する。

ローカル正式記録は `outputs/stage164-preparation/` の `purpose-real-iq.md`、`frozen-real-iq.json`、`input-files-real-iq.json`、`targeted-*.log`、`study-*.log`、`verification-private.json`。本体結果は `outputs/stage164-{source,installed}-study/`、開始時peak不足を補った同一入力のRSS観察は `outputs/stage164-{source,installed}-rss-study/` に保存する。これらは公開cloneに含まれない。

初回両5対象成功/各41既存警告/除外0、800万成分完全一致、全15,625 FFT blockの有限電力照合、固定2箇所DFTが許容内。両科学JSON/3配列一致、RSS補足も初回と同一。未知形式拒否、出力上書き拒否2、取得上書き拒否1、実profile拒否/VDIF無出力を確認。新しい科学データや配列を公開せず、単局から画像復元成功を主張しない。
