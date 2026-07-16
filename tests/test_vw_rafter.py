"""描画フェーズ (vw.rafter) のテスト。vs をモックし手書きの rafter 命令で検証する。"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

from vectorworks_plugin_repeated_rafters.document import RafterCommand


def make_rafter_command(
    origin: tuple[float, float] = (0.0, 0.0),
    angle: float = 90.0,
    span: float = 4000.0,
    overhang: float = 455.0,
    pitch: float = 21.8,
    width: float = 45.0,
    height: float = 60.0,
    rafter_class: str = '04構造-02木造-05小屋組-05垂木',
    label: str = '45×60@455',
    config: str = 'SWB',
    bearing_inset: str = '52.5',
    eave_style: str = 'vertical',
    fascia_height: str = '60',
    vertical_reference: str = 'top',
    material: str = 'Wood',
    display_2d: str = 'width',
) -> RafterCommand:
    return {
        'class': rafter_class,
        'label': label,
        'origin': list(origin),
        'angle': angle,
        'span': span,
        'overhang': overhang,
        'pitch': pitch,
        'width': width,
        'height': height,
        'config': config,
        'bearing_inset': bearing_inset,
        'eave_style': eave_style,
        'fascia_height': fascia_height,
        'vertical_reference': vertical_reference,
        'material': material,
        'display_2d': display_2d,
    }


def _make_vs_mock(plugin_available: bool = True) -> MagicMock:
    """execute_rafters() 用 vs モック。

    plugin_available=True なら CreateCustomObject は非 null を返す
    (軸組ツール FramingMember 利用可能)。
    """
    vs_mock = MagicMock()
    null_handle = object()
    non_null_handle = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.LNewObj.return_value = non_null_handle
    vs_mock.CreateCustomObject.return_value = (
        non_null_handle if plugin_available else null_handle)
    return vs_mock


def _run_execute_rafters(
    vs_mock: MagicMock, commands: list[RafterCommand]) -> int:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_repeated_rafters.vw.rafter as vw_rafter
        importlib.reload(vw_rafter)
        return vw_rafter.execute_rafters(commands)


class TestExecuteRafters:
    def test_empty_commands_return_zero(self) -> None:
        vs_mock = _make_vs_mock()
        assert _run_execute_rafters(vs_mock, []) == 0

    def test_returns_count(self) -> None:
        vs_mock = _make_vs_mock()
        count = _run_execute_rafters(vs_mock, [
            make_rafter_command(origin=(0.0, 0.0)),
            make_rafter_command(origin=(1000.0, 0.0)),
        ])
        assert count == 2

    def test_draws_with_framing_member(self) -> None:
        """垂木は軸組ツール(FramingMember)で描く。"""
        vs_mock = _make_vs_mock()
        _run_execute_rafters(vs_mock, [make_rafter_command()])
        assert vs_mock.CreateCustomObject.call_count == 1
        assert vs_mock.CreateCustomObject.call_args.args[0] == 'FramingMember'
        # StructuralMember のパス生成は使わない。
        vs_mock.CreateCustomObjectPath.assert_not_called()

    def test_places_via_rotate_and_move(self) -> None:
        """棟方向へ Rotate3D し、地廻り基準線上の配置点へ Move3D する。"""
        vs_mock = _make_vs_mock()
        rotate_calls: list[tuple[float, float, float]] = []
        move_calls: list[tuple[float, float, float]] = []
        vs_mock.Rotate3D.side_effect = (
            lambda x, y, z: rotate_calls.append((x, y, z)))
        vs_mock.Move3D.side_effect = (
            lambda x, y, z: move_calls.append((x, y, z)))

        _run_execute_rafters(vs_mock, [
            make_rafter_command(origin=(500.0, 1000.0), angle=90.0),
        ])
        # Z 回り(3 番目)に angle=90 度、平面配置点 (500,1000,0) へ移動
        assert any(abs(z - 90.0) < 1e-6 for _x, _y, z in rotate_calls)
        assert any(
            abs(x - 500.0) < 1e-6 and abs(y - 1000.0) < 1e-6 and abs(z) < 1e-6
            for x, y, z in move_calls
        )

    def test_does_not_use_story_bound(self) -> None:
        """単独 PIO のため高さバインド(SetObjectStoryBound)は呼ばない。"""
        vs_mock = _make_vs_mock()
        _run_execute_rafters(vs_mock, [make_rafter_command()])
        vs_mock.SetObjectStoryBound.assert_not_called()

    def test_sets_class(self) -> None:
        vs_mock = _make_vs_mock()
        _run_execute_rafters(vs_mock, [
            make_rafter_command(rafter_class='04構造-02木造-05小屋組-05垂木'),
        ])
        class_args = [c.args[1] for c in vs_mock.SetClass.call_args_list]
        assert '04構造-02木造-05小屋組-05垂木' in class_args

    def test_sets_type_and_section_fields(self) -> None:
        vs_mock = _make_vs_mock()
        _run_execute_rafters(vs_mock, [
            make_rafter_command(width=45.0, height=105.0, overhang=910.0,
                                label='45×105@455'),
        ])
        rfields = {(c.args[2], c.args[3]) for c in vs_mock.SetRField.call_args_list}
        assert ('type', 'rafter') in rfields
        assert ('structuralUse', 'rafter') in rfields
        assert ('width', '45') in rfields
        assert ('height', '105') in rfields
        assert ('overhang', '910') in rfields
        assert ('labelText', '45×105@455') in rfields

    def test_proxies_member_parameters(self) -> None:
        """軸組ツールからプロキシしたパラメータが同名フィールドへ転送される。"""
        vs_mock = _make_vs_mock()
        _run_execute_rafters(vs_mock, [
            make_rafter_command(
                config='DWB', bearing_inset='60', eave_style='square',
                fascia_height='45', vertical_reference='bottom',
                material='木製 SPF 軸組 MT', display_2d='widthcenter'),
        ])
        rfields = {(c.args[2], c.args[3]) for c in vs_mock.SetRField.call_args_list}
        assert ('config', 'DWB') in rfields
        assert ('bearinginset', '60') in rfields
        assert ('eavestyle', 'square') in rfields
        assert ('fasciaheight', '45') in rfields
        assert ('verticalReference', 'bottom') in rfields
        assert ('Material', '木製 SPF 軸組 MT') in rfields
        assert ('2DDisplay', 'widthcenter') in rfields

    def test_fallback_to_line_when_plugin_unavailable(self) -> None:
        """軸組ツールが使えない場合は通常線にフォールバックする。"""
        vs_mock = _make_vs_mock(plugin_available=False)
        count = _run_execute_rafters(vs_mock, [
            make_rafter_command(rafter_class='04構造-02木造-05小屋組-05垂木'),
        ])
        # フォールバックでも 1 本描画される
        assert count == 1
        # フォールバック時は SetRField を呼ばない
        vs_mock.SetRField.assert_not_called()
        # フォールバックの直線にもクラスを割り当てる
        class_args = [c.args[1] for c in vs_mock.SetClass.call_args_list]
        assert '04構造-02木造-05小屋組-05垂木' in class_args
