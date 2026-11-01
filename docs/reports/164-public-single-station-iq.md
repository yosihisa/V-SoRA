# 段階164：公開単局I/Q原本の取得と有限スペクトルの照合

- 作成日：2026-11-01
- 状態：完了
- 比較元コミット：`e32ad47a00d48532c4b3286bf33b13f582896095`

## 読者向け概要

受信機チームの実記録はまだなく、OCXO・構成・保存形式は未決定。一方、ユーザーから公開I/Qの取得・活用が許可されたため、旧164の新画像尤度案を保留したまま、実受信の単局原本へ開発順を変更した。対象はCAMRASがかにパルサー巨大パルスとして公開した短い電圧記録である。IとQは複素電圧の二成分。検波後のパワー画像とは異なる。

## 1. 目的・対象範囲

公開原本の同一byteを追跡し、符号・I/Q順序・有限FFT電力を独立計算へ照合する。既存のVDIF入口へ接続する際の具体的な制約を確認する。製品103fileと4assetsは変更しない。新規は取得ツール、検証workflow、取得配置案内、本report/索引/roadmapと検証案内。

取得元・著者・ライセンス・配置・再現コマンドは[取得案内](../guide/public-voltage-data.md)を参照。ユーザー指示に従い原本・メタデータ・派生数値配列・図をGitへ載せない。詳細な取得receipt/科学summary/環境/失敗記録はローカルの `data/raw/public/camras-crab/` と `outputs/stage164-preparation/`、`outputs/stage164-{source,installed}-study/` に置く。[公開検証案内](../../validation/runs/stage164/README.md)には方法と合否だけを記す。

## 2. 完了条件

実行前に管理外の目的記録で、URL2個/取得32 MiB/空き10 GiB/保存64 MiB、worker120秒/追加peak64 MiB、FFT256と先頭・末尾の直接DFT、RTOL1e-11/ATOL1e-8を固定した。全成分の二方式復号は完全一致を要求。真値・seed・画像係数・天体検出閾値を使わず、MC0/MCSE対象外。入力SHAとsource/tests/tools/workflowを正式前に凍結する。sourceとinstalledの科学JSON/全配列、正確なmoduleの由来とbyte、既存VDIF対象試験、上書き拒否と未知形式拒否を確認する。

## 3. 実際に行った作業

- [取得ツール](../../tools/fetch_camras_crab.py)でHTTPS取得。原本・メタデータ・receiptを既存ignore配下へ保存し、URL/byte/SHA/HTTP情報/空きを記録した。提供元公表checksumとの照合ではない。
- [workflow](../../workflows/public_iq_validation.py)は読み取り専用memmapと最大65,536sampleのchunkで処理。NumPyのlittle-endian int16と、byteからの独立した二の補数式を全成分へ適用。最初のI/Q一組はstructでも確認した。
- 全非重複FFTのParseval等式（時間側と周波数側の有限平均電力が一致）を確認。先頭/末尾256点は明示DFT行列と照合した。スペクトル配列とblock電力はローカルだけに保存。
- 実供給Fs・capture時刻を保持した4096sample prefixを現write_vdifへ渡し、profile拒否とVDIF/sidecar無出力を確認した。Fsやepochを架空値へ変更しない。

## 4. 検証条件・結果

本体16,000,000 byte、メタデータ1,954 byte、400万complex sample（800万成分）、供給Fs20 MHz・中心410 MHz、公称0.2秒。800万成分が完全一致、FFT256の15,625blockで余り0。全Parsevalおよび固定2箇所のDFTは固定許容内。天体パルスの有意検出、RFI分類、物理較正、時計精度は今回の合格対象ではない。

初回正式手順は成功。source/installed各5既存VDIF対象が0.38/0.24秒で成功、各41既存Baseband警告、除外0。対象試験内の模擬VDIF生成と、実原本主比較のVDIF無生成を区別する。新unitなし。科学JSONと3配列が両環境で完全一致。2製品moduleの正確source/prefix/byte、checkout外native runner/PYTHONPATHなしを確認した。両出力上書き拒否2、取得先上書き拒否1、未知形式拒否1。実原本を再取得していない。

study本体は約0.140/0.133秒、生涯peak RSSは92,319,744/92,897,280 byte。初回にimport時peakを記録しておらず追加メモリ予算を判定できなかったため、製品/workflow/入力/許容を固定したまま別出力でRSS観察を補足した。補足のimport後からの生涯peak増分は41,533,440/41,115,648 byteで64 MiB未満、補足科学JSON/3配列も初回へ完全一致。生涯peakの差であり、瞬間常駐量・全夜RAMの測定ではない。補足を独立観測・試行数へ加算しない。

取得開始時の空き48,100,634,624 byte、検証後48,099,217,408 byte。並行する環境の変動を含むため空き容量差をこの処理の使用量としない。原本+4study出力の実file合計16,285,759 byteで64 MiB未満。旧163凍結462、原本131の76file SHA、151wheel103file+4assetsのsource/wheel/installed全byteを保持した。新full/collect/wheel/install/browser/MC/相関/Closure/RML/画像fitなし。全回帰/両実GUIは[151](151-sequence-capacity-guard.md)の引用であり今回へ加算しない。

公開監査指摘0、文書リンク2229件で欠落0。原本・提供metadata・派生数値配列の公開0 byte、対象外tracked1548fileのSHAを保持。

## 5. 制約・未解決事項

公開元が供給する `core:datetime` と別の `dt:datetime` の意味・精度は未照合。デコードした整数は未較正ADC、電力はADC²でありJyではない。整数端点の件数も受信機clipの測定ではない。Fs20 MHzは4096sample/frameの整数frame率に合わず、現write_vdifはさらに整数秒開始を要求する。今回の実API拒否は前者で発生し、後者は現codeの条件を読んだもの。VDIF形式一般で表現不能という意味ではない。

単局で基線0。複製した架空局を作らず、実相関・Closure・Cas A画像化・独立OCXO評価へ成功を継承しない。MWA/CHIME本体は未取得。通常GUIは既報の接続拒否のままで、停止・再起動・更新していない。公開データを取得できたことは受信機チームの構成が決まった意味ではない。

## 6. 次段階

165は旧画像再fit案を保留し、公開原本のFs・小数秒epoch・電圧単位を保つ表現/変換の候補を先に比較する。VDIFの別frame長などを検討しても、I/Qや時刻の対応を仮定で隠さない。製品変更を選ぶ前に両全回帰/wheel/両実GUIを含め予算改訂する。複数アンテナの検証にはMWAの実観測ID・最小取得容量・条件を調べ、空き容量に合わせ少量だけを選ぶ。新尤度・画像再fitの前提は成立していない。
