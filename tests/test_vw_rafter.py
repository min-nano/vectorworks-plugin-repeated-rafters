"""描画フェーズ (vw.rafter) のテスト。vs をモックし手書きの rafter 命令で検証する。"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

from vectorworks_plugin_repeated_rafters.document import RafterCommand


def make_rafter_command(
    start: tuple[float, float] = (0.0, 0.0),
    end: tuple[float, float] = (0.0, 4000.0),
    width: float = 45.0,
    height: float = 60.0,
    elevation: float = 0.0,
    end_elevation: float = 1600.0,
    rafter_class: str = '04構造-02木造-05小屋組-05垂木',
    member_id: str = '45×60 - 垂木',
    profile_shape: str = 'Rectangle',
    profile_series: str = 'AISC (Inch)',
    member_type: str = '2',
    structural_use: str = '1',
    axis_align: str = '1',
    start_condition: str = '3',
    end_condition: str = '3',
    material: str = '',
) -> RafterCommand:
    return {
        'class': rafter_class,
        'member_id': member_id,
        'start': list(start),
        'end': list(end),
        'width': width,
        'height': height,
        'elevation': elevation,
        'end_elevation': end_elevation,
        'profile_shape': profile_shape,
        'profile_series': profile_series,
        'member_type': member_type,
        'structural_use': structural_use,
        'axis_align': axis_align,
        'start_condition': start_condition,
        'end_condition': end_condition,
        'material': material,
    }


def _make_vs_mock(plugin_available: bool = True) -> MagicMock:
    """execute_rafters() 用 vs モック。

    plugin_available=True なら CreateCustomObjectPath は非 null を返す
    (構造材プラグイン利用可能)。
    """
    vs_mock = MagicMock()
    null_handle = object()
    non_null_handle = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.LNewObj.return_value = non_null_handle
    vs_mock.CreateCustomObjectPath.return_value = (
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
            make_rafter_command(start=(0.0, 0.0)),
            make_rafter_command(start=(1000.0, 0.0)),
        ])
        assert count == 2

    def test_path_carries_incline_in_z(self) -> None:
        """傾き(勾配)はパスの Z 成分で表す(高さバインドは使わない)。"""
        vs_mock = _make_vs_mock()
        vertex_calls: list[tuple[float, float, float]] = []
        move3d_calls: list[tuple[float, float, float]] = []

        def capture_vertex(h: object, x: float, y: float, z: float) -> None:
            vertex_calls.append((x, y, z))

        def capture_move3d(x: float, y: float, z: float) -> None:
            move3d_calls.append((x, y, z))

        vs_mock.AddVertex3D.side_effect = capture_vertex
        vs_mock.Move3D.side_effect = capture_move3d

        _run_execute_rafters(vs_mock, [
            make_rafter_command(start=(500.0, 0.0), end=(500.0, 4000.0),
                                elevation=0.0, end_elevation=1600.0),
        ])

        # 方向ベクトルは (0, 4000, 1600)(Z=立ち上がり。傾きをパスに持たせる)
        assert vertex_calls == [
            (pytest.approx(0.0), pytest.approx(4000.0), pytest.approx(1600.0)),
        ]
        # Move3D で始端(軒側 (500,0,0))へ移動
        assert any(
            abs(x - 500.0) < 1e-6 and abs(y) < 1e-6 and abs(z) < 1e-6
            for x, y, z in move3d_calls
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

    def test_sets_member_id_and_section_fields(self) -> None:
        vs_mock = _make_vs_mock()
        _run_execute_rafters(vs_mock, [
            make_rafter_command(width=45.0, height=105.0,
                                member_id='45×105 - 垂木'),
        ])
        rfields = {(c.args[2], c.args[3]) for c in vs_mock.SetRField.call_args_list}
        assert ('MemberID', '45×105 - 垂木') in rfields
        assert ('MajorBreadth', '45') in rfields
        assert ('MajorDepth', '105') in rfields
        assert ('MinorBreadth', '45') in rfields
        assert ('MinorDepth', '105') in rfields
        assert ('ProfileShape', 'Rectangle') in rfields
        # 実在しない 'B'/'D' フィールドはもう設定しない。
        field_names = {c.args[2] for c in vs_mock.SetRField.call_args_list}
        assert 'B' not in field_names
        assert 'D' not in field_names

    def test_proxies_member_parameters(self) -> None:
        """軸組ツールからプロキシしたパラメータが同名フィールドへ転送される。"""
        vs_mock = _make_vs_mock()
        _run_execute_rafters(vs_mock, [
            make_rafter_command(
                profile_shape='Rectangle', profile_series='JIS',
                member_type='2', structural_use='4', axis_align='4',
                start_condition='2', end_condition='2',
                material='木製 SPF 軸組 MT'),
        ])
        rfields = {(c.args[2], c.args[3]) for c in vs_mock.SetRField.call_args_list}
        assert ('ProfileSeries', 'JIS') in rfields
        assert ('MemberType', '2') in rfields
        assert ('StructuralUse', '4') in rfields
        assert ('AxisAlign', '4') in rfields
        assert ('StartCondition', '2') in rfields
        assert ('EndCondition', '2') in rfields
        assert ('MemberMaterial', '木製 SPF 軸組 MT') in rfields

    def test_fallback_to_line_when_plugin_unavailable(self) -> None:
        """構造材プラグインが使えない場合は通常線にフォールバックする。"""
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
