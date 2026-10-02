# 独立検証用CASA環境

CASAは本プロジェクトの画像化結果を独立に確認し、実データを既製ソフトで扱うための任意の追加ソフトです。通常のPython環境から分けて導入します。以下はこの開発環境で実際に行った技術的な記録です。 [用語集](../guide/glossary.md)。


処理本体とは別の `.casa-venv` を使用。検証版はcasatools/casatasks **6.7.6.14**、casaconfig 1.5.2、Python 3.12。CASAデータはcasarundata-2026.02.19-1、NRAO_Measures_20261001-140644。環境・Measure tables・ログ・MSはGit管理外。

```sh
python3 -m venv .casa-venv
.casa-venv/bin/pip install casatools==6.7.6.14 casatasks==6.7.6.14
```

`.casa-venv/casasiteconfig.py` を次の内容で作る。既存ユーザー設定を使わず、更新を明示的に行う。

```python
from pathlib import Path
measurespath = str(Path.cwd() / '.casa-data')
cachedir = str(Path.cwd() / '.casa-data' / 'cache')
logfile = str(Path.cwd() / 'outputs' / 'casa.log')
data_auto_update = False
measures_auto_update = False
```

```sh
CASASITECONFIG="$PWD/.casa-venv/casasiteconfig.py" .casa-venv/bin/python -m casaconfig --noconfig --update-all
python3 tools/run_casa.py tools/verify_casa.py --input outputs/fixture/point.fits --expected outputs/fixture/expected.npz --output outputs/casa-check --image
```

このWSL環境ではCASA同梱ライブラリとシステムOpenSSLのシンボルが合わずimportに失敗した。段階006では[公式OpenSSL 3.2.6ソース](https://openssl-library.org/source/old/3.2/index.html)のSHA256 `89681a9ddaa9ed7cf25ea8ef61338db805200bae47d00510490623547380c148` を確認し、プロジェクト専用ライブラリを構築した。

```sh
# 展開したopenssl-3.2.6ソース内で実行する。PROJECTはチェックアウトの絶対パス。
./Configure shared enable-md2 no-tests --prefix="$PROJECT/.casa-ssl"
make -j8 build_libs
mkdir -p "$PROJECT/.casa-ssl/lib"
cp libcrypto.so.3 libssl.so.3 "$PROJECT/.casa-ssl/lib/"
```

`tools/run_casa.py` はこの2ファイルが存在する場合のみCASA子プロセスへLD_PRELOADする。OSのライブラリを変更していない。これは今回の互換確認に必要だった局所的対応で、OpenSSL自体のテストは未実施。環境が異なる場合はこの対応が必要とは限らない。CASA以外のプロセスや公開サービスの暗号設定には使用しない。

`tools/verify_casa.py` は検証用expected.npzを必要とする。汎用データ変換ソフトではない。公開保存するのは数値summaryと匿名化した図・入力FITSのみとし、絶対パスを含むCASAログやMS HISTORYは保存しない。
