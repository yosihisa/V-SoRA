# 段階134の画像統計契約監査

- [コード監査](source-audit.json)：17file/20記述。基準commit、行範囲、SHA、保証しないこと。
- [保存配列の目録](artifact-inventory.json)：原本76/相関12/真値4/fitter12のSHA、配列dtype/shape、局/基線count、flag、単位。36セルは診断前ゲートの候補。API/PSD/数値範囲の結果はnull。
- [一次文献](sources.json)：取得日、URL、確認した式/節、今回使用しない解釈。
- [不変性と引用](verification.json)：旧コード・過去レポート、引用した正式記録のSHA、今回未実施の検証。

この段階では新しい数値実験、試験/collect、raw生成、相関、fit、共分散API実行、wheel/導入、ブラウザ検証は行わない。ファイル読取とSHA・保存情報のゲート検査を実施した。共通countとproducerの集合定義による説明、PSDの手計算例は、新しいソフト試験や実測ではない。

原本はGit管理外outputs/stage131-source-study/、完全相関はoutputs/stage132-source-study/、fitterはoutputs/stage133-source-study-final/。再生成・再相関せず、既存公開識別情報と照合した。ローカル個人pathや完全な外部PDF本文は公開記録に保存しない。

詳しい説明は[契約](../../../interfaces/image-statistics-contract.md)と[段階レポート](../../../docs/reports/134-image-statistics-contract.md)を参照する。低SNR画像化や実機Cas Aを検証済みとしない。
