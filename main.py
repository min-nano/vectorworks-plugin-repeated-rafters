"""VectorWorks に登録する PIO のオブジェクトスクリプト本体。

このリポジトリのパッケージ(``vectorworks_plugin_repeated_rafters``)を
VectorWorks の Python Externals フォルダにインストールしたうえで、この
``main.py`` の内容を**パスプラグインオブジェクト「繰り返し垂木」のオブジェクト
スクリプト**として貼り付ける。VectorWorks はオブジェクトの再生成(リセット)の
たびにこのスクリプトを実行し、``run()`` が屋根の水平投影面(パス)とパラメータ
から垂木を描き直す。

姉妹プロジェクト vectorworks_plugin_import_ifc_homeskz の ``main.py`` は実行の
たびに GitHub の最新版を確認して自動更新するが、**PIO はオブジェクト再生成の
たびに何度も実行される**ため、ここではネットワークアクセスを一切行わず、
インストール済みのパッケージを読み込んで実行するだけにする(更新は
``pip install --upgrade`` で明示的に行う。README 参照)。
"""
from __future__ import annotations

import importlib

MODULE_NAME = "vectorworks_plugin_repeated_rafters"


def _main() -> None:
    module = importlib.import_module(MODULE_NAME)
    module.run()


_main()
