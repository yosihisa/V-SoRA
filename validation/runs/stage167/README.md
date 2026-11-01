# 段階167の検証案内

[report](../../../docs/reports/167-public-voltage-provenance.md)を参照。今回は公開候補の出典・取得条件の監査で、新数値試験・模擬電圧生成・本体取得は行わない。

管理外 `outputs/stage167-preparation/` の `purpose-draft.md` は探索前のHTTP上限と除外操作、`purpose-fixed.md` は候補監査の範囲、`input-files.json` は取得24fileのSHA、`frozen.json` は全Pythonの基準。`discovery/receipt.json` にURL・UTC・byte・SHA・失敗を保存する。検索HTMLや提供metadataをこのディレクトリへコピーしない。

MWA試験fixtureの生成コードと変更metafitsを実観測と区別した。LWA論文の実TBN条件を、配布ファイル取得済みと区別した。匿名検索0行はデータの不存在の証明ではない。再確認する際はreportの固定commit出典・公式案内を読み、原本取得の前に具体的ファイルと最小容量・利用条件を固定する。

数値回帰、full/wheel/実GUI/MC/相関/画像の今回成功件数は0。前段の結果を再加算しない。
