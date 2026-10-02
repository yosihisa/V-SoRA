# 日本語の観測解析GUI

WSL UbuntuでPythonの処理を動かし、Windowsのブラウザで操作します。模擬観測、重要な検証、実行履歴、画像・数値・ファイル保存を扱います。[利用ガイド](../../docs/guide/06-gui.md)を参照してください。

実装はFastAPI、HTML/CSS/JavaScriptです。JavaScriptのビルド工程はなく、科学処理は別Python processへ渡します。日本語フォントはOFL公開フォントを同梱しています。

収録データの解析とClosure＋RMLは後続段階で追加します。局利得を高精度に較正できることを、実観測の完成条件には置きません。
