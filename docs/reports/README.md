# 開発段階レポート

開発段階ごとに目的、実際の作業、検証結果、未解決事項を記録し、その段階の変更と一緒にコミットする。

| 段階 | レポート | 状態 |
| --- | --- | --- |
| 000 | [初期整理・開発構想](000-initial-plan.md) | 調査・設計の初期記録。ソフト実装と動作検証は未実施 |
| 001 | [共通入力・参照画像](001-foundation.md) | 12件の検証成功。ソフト別構成へ移行 |
| 002 | [理想visibility・画像復元](002-ideal-imaging.md) | 22件成功。点源・2点源の解析比較とFITS画像出力 |
| 003 | [Cas A・局配置比較](003-casa-array-study.md) | 24件成功。7条件を比較、リング配置はCLEAN非収束 |
| 004 | [VDIF・FX相関](004-vdif-fx.md) | 30件成功。短時間IQの量子化・遅延・相関を検証 |
| 005 | [IQから画像まで](005-iq-to-image.md) | 33件成功。8局・16snapshotをVDIF→IDI候補→画像へ接続 |
| 006 | [CASA独立互換確認](006-casa-compatibility.md) | 33件成功。共役を修正、偏心点源の位置・振幅と重みを確認 |
| 007 | [未知の局応答の較正](007-fringe-calibration.md) | 39件成功。5seedで別Cas A観測のvisibility誤差0.9～1.2% |
| 008 | [IQの未知LO差と再相関](008-iq-fringe-tracking.md) | 44件成功。2passで平均visibility誤差0.60%、VDIF frame iterator |
| 009 | [ADC時計・分数sample整列](009-adc-clock-alignment.md) | 48件成功。連続解析波形で時計推定・補間・幾何の符号を検証 |
| 010 | [session・相関CLI](010-session-cli.md) | 52件成功。ADC→2pass較正→Jy/IDI→画像、stream/shard保存 |
| 011 | [独立環境・wheel導入](011-reproducible-environment.md) | 独立venvで52件成功。checkout外の参照画像・CLI実行を確認 |
| 012 | [Cas Aモデル較正](012-casa-model-calibration.md) | 55件成功。spanning tree、2感度条件の16snapshot、prior依存を明示 |
| 013 | [多channel IDI・正確なCLEAN](013-spectral-idi-exact-clean.md) | 57件成功。CASA8channel、偏心点源の発散を修正して66回で収束 |
| 014 | [時計・幾何sample整列](014-stream-clock-geometry.md) | 58件成功。VDIFのclock/RF補正、buffer8197sample、EOF拒否 |

| 015 | [短いpilot積分・入力検査](015-short-pilot-input-validation.md) | 68件成功。1ms積分・設定誤字・FITS溢れを検査 |

| 016 | [実データ用CASAアダプター](016-casa-production-adapter.md) | 71件成功。actual FITSのchannel重み・flagをMSへ保持 |

| 017 | [周波数別重み・RFI診断](017-spectral-quality-rfi.md) | 80件成功。模擬RFI誤差996%→4.77%、有限雑音試験の誤flag0 |

| 018 | [学部生向け文書](018-undergraduate-documentation.md) | 原理・用語・結果の意味を整理。リンク切れ0、点源手順を再実行 |

新しいレポートは [テンプレート](templates/stage-report.md) を使用する。段階の対象コミットは、そのレポートを追加・更新したGit履歴から確認できる。
