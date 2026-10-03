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

| 019 | [日本語ブラウザGUI](019-japanese-browser-gui.md) | 90件成功。Chromium実操作・日本語font・画像表示・中止・wheelを確認 |

| 020 | [Closure・短積分の周波数差](020-closure-short-integration.md) | 98件成功。局利得不変性、独立共分散、0.3秒IQのLO損失と補正 |

| 021 | [Closure＋RML・日本語GUI](021-closure-rml-reference.md) | 105件成功。相対flux、未知局利得、短露光・事前依存、Cas A上限到達を記録 |

| 022 | [モデル不要のLO差推定](022-model-free-rate.md) | 111件成功。未知sky/gain、短pilot、3seedのIQ補正後Closure、欠損graph |

| 023 | [VDIFからClosure＋RML・解析GUI](023-vdif-closure-pipeline.md) | source/wheel115件成功。未知flux、sample/幾何/rate、partial、checkout外CLI/GUI |

| 024 | [短露光VDIF合成・感度不足](024-vdif-synthesis.md) | source/wheel121件成功。8局Cas A高感度仮定で形状誤差2.8%、低感度失敗とRML上限を記録 |

| 025 | [短積分の感度計画](025-sensitivity-planning.md) | source125件成功。32期待値条件・アンテナ換算・日本語感度GUI。実機感度は未測定 |

| 026 | [相関の分割処理](026-bounded-fx.md) | source/wheel129件成功。8局1秒の統計を保持し、peak RSS約1.42GiB→325MiB |

| 027 | [3秒pilot・分割幾何](027-three-second-pilot.md) | source130件成功。4局3秒VDIFとGUI、rate誤差0.0015Hz。実OCXO安定時間は未測定 |

| 028 | [Cas Aの3秒合成・低感度](028-casa-three-second-sensitivity.md) | source130件成功。8時刻処理完了、形状誤差34〜37%で画像の良好復元は未確認 |

| 029 | [短い刻みの広範囲LO探索](029-wide-rate-pilot.md) | source/wheel140件成功。1185Hz基線差をVDIFから補正、SK未判定と検出不能aliasを記録 |

| 030 | [全成分を保持した位置合わせ評価](030-full-support-registration.md) | source/wheel151件成功。固定Cas A画像の高感度2.36%、低感度35〜39%。復元画像は変更せず |

| 031 | [guard付きVDIF部分読取](031-guarded-vdif-seek.md) | source/wheel157件成功。後方区間の相関差0、decoded frame1402→152。未読prefixの範囲を明示 |

| 032 | [短window列・LO再推定](032-short-window-sequence.md) | source/wheel162件成功。同一VDIFの3区間でLO差変化を推定、露光0.9秒。選択RMLは800反復上限 |

新しいレポートは [テンプレート](templates/stage-report.md) を使用する。段階の対象コミットは、そのレポートを追加・更新したGit履歴から確認できる。
