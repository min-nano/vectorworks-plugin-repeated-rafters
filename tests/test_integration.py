"""統合テスト: ジオメトリ計算 → JSON 直列化 → 描画 の一連を検証する。"""
from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock, patch

from vectorworks_plugin_repeated_rafters.rafters import build_document

RECT = [[0.0, 0.0], [6000.0, 0.0], [6000.0, 4000.0], [0.0, 4000.0]]
CLASS = '04構造-02木造-05小屋組-05垂木'
# 軸組ツール(FramingMember)からプロキシするパラメータの既定(統合テスト用)。
MEMBER_PARAMS: dict = {
    'config': 'SWB',
    'bearing_inset': '52.5',
    'eave_style': 'vertical',
    'fascia_height': '60',
    'vertical_reference': 'top',
    'material': 'Wood',
}


def _make_vs_mock() -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    non_null = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.LNewObj.return_value = non_null
    vs_mock.CreateCustomObject.return_value = non_null
    return vs_mock


def test_build_document_is_json_serializable() -> None:
    doc = build_document(
        RECT, base_line=None, slope=4.0, width=45.0, height=60.0,
        spacing=1000.0, rafter_class=CLASS, **MEMBER_PARAMS)
    # 直列化して戻しても等価(vs ハンドル等の非直列化値を含まない)
    assert json.loads(json.dumps(doc)) == doc


def test_full_pipeline_draws_all_rafters() -> None:
    doc = build_document(
        RECT, base_line=None, slope=4.0, width=45.0, height=60.0,
        spacing=1000.0, rafter_class=CLASS, **MEMBER_PARAMS)
    doc = json.loads(json.dumps(doc))

    vs_mock = _make_vs_mock()
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_repeated_rafters.vw.rafter as vw_rafter
        import vectorworks_plugin_repeated_rafters.vw as vw
        importlib.reload(vw_rafter)
        importlib.reload(vw)
        counts = vw.execute_document(doc)

    assert counts['rafters'] == len(doc['rafters']) == 7
    assert vs_mock.CreateCustomObject.call_count == 7
