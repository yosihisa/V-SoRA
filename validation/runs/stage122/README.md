# 段階122の正式記録

[レポート](../../../docs/reports/122-ehtim-convention-bridge.md)の数値・導入・制約を記録する。

- [verification.json](verification.json)：39対象/collect/引用した全回帰、prefix・非上書き・byte照合。
- [reference.json](reference.json)：nativeの20画像条件、3周波数、現存入力のw項モデル差27条件と原本SHA。
- [external.json](external.json)：実EHTimのDFT/Closure/周辺近似σ/gain、原本API失敗と明示した型接続部。
- [artifact.json](artifact.json)：固定版配布物のSHA、license、公式tag4ファイルとの一致。
- [w-model-bound.png](w-model-bound.png)：総flux1のモデル差。実測の相関誤差や復元画像の精度ではない。

再現にはリポジトリのvalidation workflowと、Git管理外の現存118入力3ファイルが必要である。作業フォルダをcheckout外にできることを、checkoutも不要な製品機能と読み替えない。`outputs/stage122-preparation/`に正式目的・進行記録・対象試験・導入ログ・初回の外部API失敗、`outputs/stage122-source-study/`に49配列の参照bundle、`outputs/stage122-installed-api/`にcheckout外のnative再生成と外部実行、`outputs/stage122-external-env/`に独立環境、`outputs/stage122-external-artifacts/`に配布物を保存した。初回・予備結果を正式成功件数へ合算しない。
