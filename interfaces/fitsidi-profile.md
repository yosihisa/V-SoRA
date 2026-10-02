# FITS-IDI出力の限定profile

[AIPS Memo 114](https://www.aips.nrao.edu/TEXT/PUBL/AIPSMEM114.PDF) に基づく候補出力。ARRAY_GEOMETRY、FREQUENCY、SOURCE、ANTENNA、UV_DATAと独自VSORA_METAを保存する。

- 一つのsource/band、単一XX、平均したcontinuum1channel。帯域は2.048 MHzを仮定。
- **profile v2**：FITS内uvwは内部uvwの負、光秒単位。FLUXは内部visibilityの複素共役。CASA importfitsidiで内部visibilityへ戻り、偏心点源が正しい位置になることを確認。内部readerも共役を戻す。
- 段階005のv1は内部読み戻しだけを確認した旧形式。CASAで画像が反転した。保存済み段階005のFITSをCASAに直接渡さず、v2へ再出力する。
- BASELINE=256*antenna1+antenna2、antenna番号は1から。
- DATEはUTC日の0時のJulian date、TIMEはその日の割合。INTTIMは実サンプルから計算した露光時間。
- FLUXは実部・虚部・重みの3要素、WEIGHTYP=NORMAL、重みはJy^-2の逆分散。ゼロ重みは無効。重みでvisibilityを割らない。
- **CASAはimport時に重みを再初期化する**。検証ツールは入力の逆分散をWEIGHT/SIGMAへ明示的に復元。実用converterでも同じ処理が必要。
- sourceのICRS座標をFK5/J2000に変換して記録。CASA import時に `coordframe='J2000'` を指定。模擬幾何の接平面軸の厳密な変換は実観測モデルとして未完成。
- sourceのIFLUX等は未知として0を保存。単一XXから完全なStokes Iを測ったとは扱わない。
- 独自readerはVSORA_METAを必要とする。他装置の一般FITS-IDI readerとしては未対応。

段階006でCASA 6.7.6.14による読込み、uvw/時刻/局番号、重みの復元、偏心点源の画像位置と明るさを確認。アンテナ直径は未知なら0、主ビームは未提供。AIPSや複数周波数・偏波は未検証。profileの拡張が必要な入力は黙って近似せず、未対応として扱う。
