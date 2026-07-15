"""PIO オブジェクトスクリプト本体 (run) と vs 読み取りヘルパーのテスト。"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

import vectorworks_plugin_repeated_rafters as pkg

RECT = [(0.0, 0.0), (6000.0, 0.0), (6000.0, 4000.0), (0.0, 4000.0)]


def _make_vs_mock(
    info_ok: bool = True,
    params: dict[str, str] | None = None,
    vertices: list[tuple[float, float]] | None = None,
) -> MagicMock:
    verts = RECT if vertices is None else vertices
    values = {
        'BaseEdge': '1',
        'Slope': '4',
        'Width': '45',
        'Height': '60',
        'Spacing': '2000',
        'RafterClass': '',
    }
    if params:
        values.update(params)

    vs_mock = MagicMock()
    null_handle = object()
    obj_handle = object()
    path_handle = object()
    non_null = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.GetCustomObjectInfo.return_value = (
        info_ok, obj_handle, object(), object())
    vs_mock.GetCustomObjectPath.return_value = path_handle
    vs_mock.GetVertNum.return_value = len(verts)
    vs_mock.GetPolylineVertex.side_effect = (
        lambda h, i: (verts[i - 1], 0, 0.0))
    vs_mock.GetRField.side_effect = (
        lambda obj, plugin, field: values.get(field, ''))
    vs_mock.LNewObj.return_value = non_null
    vs_mock.CreateCustomObjectPath.return_value = non_null
    return vs_mock


class TestReadHelpers:
    def test_read_path_points(self) -> None:
        vs_mock = _make_vs_mock()
        obj = object()
        pts = pkg._read_path_points(vs_mock, obj)
        assert pts == [[0.0, 0.0], [6000.0, 0.0], [6000.0, 4000.0], [0.0, 4000.0]]

    def test_read_path_points_empty_when_no_path(self) -> None:
        vs_mock = _make_vs_mock()
        vs_mock.GetCustomObjectPath.return_value = vs_mock.Handle.return_value
        assert pkg._read_path_points(vs_mock, object()) == []

    def test_read_parameters_uses_defaults_for_blank_class(self) -> None:
        vs_mock = _make_vs_mock(params={'RafterClass': ''})
        params = pkg._read_parameters(vs_mock, object())
        assert params['rafter_class'] == pkg.DEFAULT_CLASS
        assert params['base_edge'] == 1
        assert params['slope'] == 4.0
        assert params['width'] == 45.0
        assert params['height'] == 60.0
        assert params['spacing'] == 2000.0

    def test_read_parameters_custom_class(self) -> None:
        vs_mock = _make_vs_mock(params={'RafterClass': '垂木クラス'})
        params = pkg._read_parameters(vs_mock, object())
        assert params['rafter_class'] == '垂木クラス'

    def test_read_parameters_falls_back_on_invalid(self) -> None:
        vs_mock = _make_vs_mock(params={'Slope': 'abc', 'BaseEdge': ''})
        params = pkg._read_parameters(vs_mock, object())
        assert params['slope'] == pkg.DEFAULT_SLOPE
        assert params['base_edge'] == pkg.DEFAULT_BASE_EDGE


def _run(vs_mock: MagicMock) -> None:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_repeated_rafters.vw.rafter as vw_rafter
        import vectorworks_plugin_repeated_rafters.vw as vw
        importlib.reload(vw_rafter)
        importlib.reload(vw)
        importlib.reload(pkg)
        pkg.run()


class TestRun:
    def test_run_draws_rafters(self) -> None:
        vs_mock = _make_vs_mock(params={'Spacing': '2000'})
        _run(vs_mock)
        # 長方形 6000 幅 / 間隔 2000 → 4 本の構造材を配置
        assert vs_mock.CreateCustomObjectPath.call_count == 4

    def test_run_returns_early_when_info_not_ok(self) -> None:
        vs_mock = _make_vs_mock(info_ok=False)
        _run(vs_mock)
        vs_mock.CreateCustomObjectPath.assert_not_called()

    def test_run_handles_missing_path(self) -> None:
        vs_mock = _make_vs_mock()
        vs_mock.GetCustomObjectPath.return_value = vs_mock.Handle.return_value
        _run(vs_mock)
        # パスが無ければ垂木は 1 本も描かない
        vs_mock.CreateCustomObjectPath.assert_not_called()


def teardown_module(module: object) -> None:
    # 他テストへ影響しないよう、モック無しで本体パッケージを読み直す
    importlib.reload(pkg)
