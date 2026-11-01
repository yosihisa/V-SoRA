# 段階166の検証案内

[report](../../../docs/reports/166-public-iq-samplebuffer.md)と[取得配置・実行方法](../../../docs/guide/public-voltage-data.md)を参照。

原本・提供metadata・receipt・出力電圧・query/tapsを含む数値配列・科学summaryはGit管理外。公開するのは方法と合否の文章である。

実行前固定は `outputs/stage166-preparation/purpose-fixed.md`、`input-files.json`、`frozen.json`。sourceは `tools/run.py workflows.public_samplebuffer_validation`、installedは既存wheel環境でcheckout外cwd/PYTHONPATHなし、workflowを絶対pathで指定する。146・周期参照・164のhelperもcheckoutに必要である。

固定4窓×seek/順次の8条件を既存SampleBufferへ通す。独立有限畳み込み・補間式とRTOL1e-11/ATOL1e-8 ADCで照合。原本外query拒否2、初期FIR支持不足のmask/zero、上書き拒否2を確認した。両既存9対象/各41既存警告/除外0、科学JSON/17配列と21moduleの正確origin/byteが一致。初回正式成功で、新相関/画像/時計推定はない。

ローカル結果は `outputs/stage166-{source,installed}-study/`、正式ログ/worker時間/メモリ/容量/原本SHA/公開監査は `outputs/stage166-preparation/` に保存する。これらは公開cloneに含まれない。
