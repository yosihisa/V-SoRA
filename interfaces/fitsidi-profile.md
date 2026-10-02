# FITS-IDI出力の限定profile

[AIPS Memo 114](https://www.aips.nrao.edu/TEXT/PUBL/AIPSMEM114.PDF) に基づく候補出力。ARRAY_GEOMETRY、FREQUENCY、SOURCE、ANTENNA、UV_DATAと独自VSORA_METAを保存する。

- 一つのsource/band、単一XX、平均したcontinuum1channel。帯域は2.048 MHzを仮定。
- visibilityはfirst×conj(second)。標準のuvwはfirst−secondなので内部uvwから符号を反転し、光秒に変換。自分の読込み時に戻す。
- BASELINE=256*antenna1+antenna2、antenna番号は1から。
- DATEはUTC日の0時のJulian date、TIMEはその日の割合。INTTIMは実サンプルから計算した露光時間。
- FLUXは実部・虚部・重みの3要素、WEIGHTYP=NORMAL。ゼロ重みは無効。重みでvisibilityを割らない。
- sourceのICRS座標をFK5/J2000に変換して記録。模擬幾何の接平面軸の厳密な変換は実観測モデルとして未完成。
- sourceのIFLUX等は未知として0を保存。単一XXから完全なStokes Iを測ったとは扱わない。
- 独自readerはVSORA_METAを必要とする。他装置の一般FITS-IDI readerとしては未対応。

段階005では構造・checksum・内部読み戻し・画像化を確認。CASA/AIPSの外部受入れは別段階で確認する。profileの拡張が必要な入力は黙って近似せず、未対応として扱う。
