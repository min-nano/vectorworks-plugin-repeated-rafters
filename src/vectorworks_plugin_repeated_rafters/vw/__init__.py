"""フェーズ2: VectorWorks 描画。

JSON 命令セット(``document.py`` のスキーマ参照)に従って vs モジュールで
実際の描画を行う。このパッケージだけが vs に依存し、ジオメトリ計算の知識は
持たない。
"""
from __future__ import annotations

from typing import Any

from ..document import validate_document
from .rafter import execute_rafters

__all__ = ['execute_document', 'execute_rafters']


def execute_document(document: Any) -> dict[str, int]:
    """命令セットを検証し、垂木を描画して実行数を返す。

    Returns: {'rafters': 配置した垂木(軸組)の本数}
    """
    validated = validate_document(document)
    return {
        'rafters': execute_rafters(validated['rafters']),
    }
