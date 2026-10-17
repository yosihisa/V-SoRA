# VDIF相関から共通電力を保存する

段階091から、VDIF相関の追加保存オプションは三局に共通するFFT標本の電力和を[raw profile version2](bispectrum-power-v2.md)へ残す。元の相関ファイルshard-00000.npzとraw-bispectrum.npzを一緒に保持する。再解析には元IQ/VDIF、時計・LO・品質処理の来歴も必要である。

CLIのcorrelate-alignedへ--save-bispectrumを付けるか、既存の解析/短区間列GUIで「再解析用の三次統計も保存する」を選ぶ。追加保存offではrawファイルを作らない。既存visibilityと現在のClosure+RMLを使う画像処理は変わらない。

保存summaryのschema_versionは2で、common_station_power_savedとcommon_power_sum_unitを含む。原本SHA、軸、局、FFT、単位、標本数、品質maskとの照合を維持する。[比の定義](common-bispectrum-power.md)と[状態の説明](bispectrum-power-v2.md)を参照。保存した二つのファイルは既存のvsora-bispectrum-inspectで検査し、JSONで正規化比を取得できる。

M<3、電力0、旧版の情報欠落を0で補完しない。数値availableと品質usableを分ける。一定gain・固定maskの条件で比が変わらない性質だけで、時間変動LOや選別の影響を解決したとは扱わない。比の不偏性・位相信頼区間・低SNR画像尤度は未確認で、現在のRMLには投入しない。

この段階ではCLI/保存を接続する。共通電力と無次元比を追加する日本語表示、およびその実ブラウザ確認は092で行う。
