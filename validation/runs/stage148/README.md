# 段階148：取得contextと入力根拠の読取り監査

[レポート](../../../docs/reports/148-real-input-evidence.md)、[人向け引渡し票](../../../docs/guide/real-input-handoff-template.md)を参照。製品parser/preflightや機器取得機能を追加した記録ではない。

- [availability.json](availability.json)：通常/承認付きread-onlyのLinux metadata確認。USB sysfs/device nodeとPATHの固定6ツール、WSL markerだけを記録し、SDRをopen/init/capture/resetしていない。二つの実行条件は物理ホスト全体やsource/installed検証を意味しない。serial/hostname/ツール絶対pathを公開していない。
- [input-provenance.json](input-provenance.json)：131 canonical4件の76SHAと44 metadata。来歴、供給clock/scale、仮定SEFD、設定UTC/RF、模擬sidecarの宣言を分離。32 VDIFはhash照合で、新decode/header検査は無い。
- [source-audit.json](source-audit.json)：6file/14関数のAST行範囲とSHA、引用23ファイルのSHA。製品関数の新呼出しは無い。
- [verification.json](verification.json)：対象外不変・凍結451・原本76、文書/公開監査。138 full/wheel/GUIと147対象は引用のみ。

同じ範囲の再点検は、記録したsystem pathの可視性と`shutil.which`の固定ツール名、列挙したファイルのSHA/JSON/AST、`tools/check_docs.py`、strictallowlist staging後の`tools/audit_public.py`で行える。機器を開くコマンドを追加したり、USB到着時刻をsample0の根拠にしない。Git外の確認script/全記録は`outputs/stage148-preparation/`、継続記録は`outputs/development-continuation.md`に保存。

実記録の所在や取得環境を照会したが、この段階は回答を前提にした測定を実施していない。現在のcontextから見えないことを、装置が存在しないと断定する資料にしない。
