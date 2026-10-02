# FITS-IDI出力の限定profile

FITS-IDIには二局の複素相関値と、局・天体・時刻・周波数・統計的な重みを保存します。ここでは扱える条件を限定し、CASAへ渡したときにも画像の位置と明るさが一致する規約を決めています。 [用語集](../docs/guide/glossary.md)。


[AIPS Memo 114](https://www.aips.nrao.edu/TEXT/PUBL/AIPSMEM114.PDF) に基づく候補出力。ARRAY_GEOMETRY、FREQUENCY、SOURCE、ANTENNA、UV_DATAと独自VSORA_METAを保存する。

- 一つのsource/band、単一XX。continuum1channelはv2、昇順・等間隔の複数channelはv3。帯域とchannel間隔は入力から記録。
- **profile v2**：FITS内uvwは内部uvwの負、光秒単位。FLUXは内部visibilityの複素共役。CASA importfitsidiで内部visibilityへ戻り、偏心点源が正しい位置になることを確認。内部readerも共役を戻す。
- 段階005のv1は内部読み戻しだけを確認した旧形式。CASAで画像が反転した。保存済み段階005のFITSをCASAに直接渡さず、v2へ再出力する。
- BASELINE=256*antenna1+antenna2、antenna番号は1から。
- DATEはUTC日の0時のJulian date、TIMEはその日の割合。INTTIMは実サンプルから計算した露光時間。
- FLUXは実部・虚部・重みの3要素、WEIGHTYP=NORMAL、重みはJy^-2の逆分散。ゼロ重みは無効。重みでvisibilityを割らない。
- v3のFLUXはcomplex/stokes/channel/band/RA/DEC軸。channelごとの逆分散と無効flagを保持。FITS内uvwは周波数に依存しない光秒、読込み時に各RF周波数のlambdaへ変換。
- **CASAはimport時に重みを再初期化する**。段階016の実用アダプターはFITS自身から逆分散を抽出し、WEIGHT/SIGMAとWEIGHT_SPECTRUM/SIGMA_SPECTRUMへ明示的に復元する。
- sourceのICRS座標をFK5/J2000に変換して記録。CASA import時に `coordframe='J2000'` を指定。模擬幾何の接平面軸の厳密な変換は実観測モデルとして未完成。
- sourceのIFLUX等は未知として0を保存。単一XXから完全なStokes Iを測ったとは扱わない。
- 独自readerはVSORA_METAを必要とする。他装置の一般FITS-IDI readerとしては未対応。

段階006で単一channel、段階013で8channel/異なる重み/無効channelをCASA 6.7.6.14で確認。uvw/時刻/局番号/周波数/flags、WEIGHT_SPECTRUM/SIGMA_SPECTRUM復元、偏心点源の位置と明るさが一致した。アンテナ直径は未知なら0、主ビームは未提供。AIPS・複数偏波・複数source/bandは未検証。未対応profileは黙って近似しない。

## CASA Measurement Setへの変換

```sh
python tools/run.py vsora_correlator casa-input --input calibrated/spectral-visibility.fits --output outputs/casa-bridge.npz
python tools/run_casa.py tools/import_casa.py --input calibrated/spectral-visibility.fits --bridge outputs/casa-bridge.npz --output outputs/casa-ms
```

simulationの期待値ファイルは不要。bridgeは入力FITSのチェックサムとprofileを検査し、SHA256、実値、重み、flagsを保持する。CASA側で入力SHA256と変換後のDATA/UVW/局番号/時刻/周波数/露光を照合してから重みを復元する。`summary.json`のstate=completeを完了条件とする。失敗directoryはincompleteを残し、再実行は別outputを指定する。

`--image`は128pixel/16arcsec/XX/niter=0のdirty画像を生成する確認オプション。科学的画像復元の条件は別途選ぶ。CASA環境は[導入記録](../docs/design/casa-environment.md)を参照。bridgeとMSはshard単位のメモリ処理であり、全観測を一度にメモリへ載せる用途は未確認。
