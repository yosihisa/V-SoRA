# RTL-SDR・600 m基線によるCas A観測：構成の初期調査

この文書は開発開始時の資料調査です。受信電圧を保存するVDIF、局間の複素相関値を保存するFITS-IDI、画像復元を担当するソフトの役割を調べました。実装後の検証は段階レポートで確認できます。 [用語集](../guide/glossary.md)。


調査日：2026-10-02。公式仕様・ソフトウェア資料を中心とした概略調査であり、受信機の実測やソフトウェアの接続試験は未実施。

## 結論

提案されたパイプラインは妥当。VDIFはVLBIの標準的な生データ交換形式、FITS-IDIはVLBI相関結果を渡すための標準形式で、DiFXとCASAを利用する接続経路がある。ただし、600 mという基線長でも時刻・位相・遅延の管理は必要。実機で画像を得られるかは周波数、アンテナ感度、局数・配置、クロック構成などが未確定のため判定できない。

```text
RTL-SDR + クロック・時刻基準
  → IQ + サンプル番号・時刻対応・観測メタデータ
  → 自作変換（必要に応じて時刻整合・リサンプリング）
  → VDIF + 局位置・周波数・偏波・時計補正等の観測設定
  → 相関器（幾何遅延補正・フリンジ回転・相互相関・積分）
  → FITS-IDI
  → 較正（残留遅延・周波数ずれ・位相・振幅・バンドパス、RFI除去）
  → 画像復元 → 画像FITS
```

CASAを使う場合、FITS-IDIを `importfitsidi` でMeasurement Setへ変換し、その上で較正・画像復元する。[3][5][6]

## 形式と既存ソフト

| 項目 | 評価・補足 |
| --- | --- |
| VDIF | 採用は妥当。実数・複素数サンプルに対応。RTL-SDRのIQをそのままファイルに包むだけではなく、量子化符号、I/Q順序、フレーム長、時刻の意味を合わせる必要がある。[1][2] |
| DiFX | 既製相関器の有力候補。VDIFに対応し、相関後の専用出力を `difx2fits` でFITS-IDIへ変換する。観測・局・周波数設定と遅延モデルも必要。採用する複素8 bit VDIFなどの具体的モードは接続試験で確認する。[2] |
| FITS-IDI | VLBI向けの交換・保存形式として妥当。visibilityだけでなく局、周波数、天体、時刻、UVW等を正しく渡す必要がある。電波干渉計全体ではMeasurement SetやUVFITSも使われる。[3][4] |
| CASA | FITS-IDI取込み、残留遅延・レートのフリンジフィット、較正、CLEAN画像復元の経路がある。自作相関器とDiFXでは量子化補正の適用条件が異なるため、相関器情報と振幅規約も確認する。[3][5][6] |

## 先に確認したい物理条件

1. **OCXOと時刻同期**：各局の独立OCXOは安定な周波数基準になり得るが、共通のサンプル開始時刻・位相を保証しない。ADCとチューナーのどこに基準が届くか、局間の周波数差・サンプルレート差・ドリフトを測定し、必要な補正を決める。
2. **タイムスタンプの由来**：通常のlibrtlsdr受信APIはデータと長さを渡し、ADCサンプルに対応するハードウェア時刻は渡さない。PCでのUSB受信時刻をサンプル時刻と同一視できない、という設計上の判断になる。改造機の追加機能は未確認。PPS等を実サンプル番号へ対応付ける方法、または相関による時刻差推定と、その不確かさの管理が必要。[7]
3. **欠損と連続性**：サンプル欠落で以降の時刻対応が崩れる。欠落検出・記録・無効区間の扱いが必要。公式APIは2.4 MS/sを超える設定でサンプル損失が予想されると記すが、それ以下でも実機・収録環境の検証が必要。[7]
4. **分解能と感度**：Cas Aはおよそ5分角の広がりを持つ。[8] `θ ≈ λ/B` とB=600 mから計算すると、150 MHzで約11.5分角、600 MHzで約2.9分角、1.4 GHzで約1.2分角。実際には投影基線・配置・重み付けに依存する。150 MHzでは形態復元が難しく、より高い周波数なら大まかな構造を分解できる可能性がある。感度はアンテナ有効面積、雑音温度、帯域、積分時間と、その基線に残る相関フラックスから別途評価する。
5. **局数と配置**：最大基線長だけでは画像品質を決められない。短い基線も含めたuv被覆が必要で、局数・配置・地球自転による観測時間をシミュレーターで評価する。

## 次の調査・実装候補

1. 観測周波数・アンテナ・局数と配置から、感度と復元可能な構造を評価。
2. OCXO改造機の時刻・周波数・欠損管理を設計し、共通信号で2受信機を検証。
3. IQ→VDIFの最小仕様を決め、既存デコーダー・DiFXで互換性を確認。
4. 相関→FITS-IDI→CASAの最小接続をシミュレーションで確認。

今回の調査では方式を確定しておらず、ソフトの導入・実装も行っていない。

## 参照資料

- [1] [IVS：VDIF仕様・関連資料](https://vlbi.org/vlbi-standards/vdif/)
- [2] [DiFX：対応形式](https://difx.readthedocs.io/en/stable/sources/difx_formats.html)、[プログラムガイド（difx2fits / vex2difx / calcif2）](https://difx.readthedocs.io/en/stable/sources/difx_programs.html)
- [3] [CASA：importfitsidi](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.data.importfitsidi.html)
- [4] [NRAO/AIPS：FITS-IDI仕様](https://www.aips.nrao.edu/FITS-IDI.html)
- [5] [CASA：fringefit](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.calibration.fringefit.html)
- [6] [CASA：tclean](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.imaging.tclean.html)
- [7] [Osmocom：librtlsdr API](https://github.com/osmocom/rtl-sdr/blob/master/include/rtl-sdr.h)、[rtl_sdr収録実装](https://github.com/osmocom/rtl-sdr/blob/master/src/rtl_sdr.c)
- [8] [Green超新星残骸カタログ：Cas A（NASA LAMBDA保存版）](https://lambda.gsfc.nasa.gov/product/websites/AMI/mrao.cam.ac.uk/surveys/snrs/snrs.G111.7-2.1.html)。2004年版のため角サイズの概略にのみ使用し、当時のフラックスを現在値とは扱わない。
