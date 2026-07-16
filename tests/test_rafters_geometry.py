"""ジオメトリ計算フェーズ (rafters) のテスト。vs 非依存。"""
from __future__ import annotations

import math

import pytest

from vectorworks_plugin_repeated_rafters.rafters import build_document
from vectorworks_plugin_repeated_rafters.rafters.geometry import (
    build_rafter_commands,
    make_label,
)

# 反時計回りの長方形(幅 6000 × 奥行 4000)。辺 1 = 下辺 (0,0)->(6000,0)。
RECT = [[0.0, 0.0], [6000.0, 0.0], [6000.0, 4000.0], [0.0, 4000.0]]

CLASS = '04構造-02木造-05小屋組-05垂木'


# 軸組ツール(FramingMember)からプロキシするパラメータの既定(ジオメトリテスト用)。
MEMBER_PARAMS: dict = {
    'config': 'SWB',
    'bearing_inset': '52.5',
    'eave_style': 'vertical',
    'fascia_height': '60',
    'vertical_reference': 'top',
    'material': 'Wood',
}


def _pitch(slope: float) -> float:
    """寸勾配から勾配角(度)を求める(テスト用の期待値計算)。"""
    return math.degrees(math.atan(slope / 10.0))


def _build(path: list[list[float]], **kwargs: object) -> list:
    params: dict = {
        'base_line': None,   # 既定はフォールバック(パスの最初の辺)
        'slope': 4.0,
        'width': 45.0,
        'height': 60.0,
        'spacing': 1000.0,
        'rafter_class': CLASS,
        **MEMBER_PARAMS,
    }
    params.update(kwargs)
    return build_rafter_commands(path, **params)


class TestMakeLabel:
    def test_integer_dimensions_have_no_decimal(self) -> None:
        assert make_label(45.0, 60.0, 455.0) == '45×60@455'

    def test_non_integer_dimensions_kept(self) -> None:
        assert make_label(45.5, 60.0, 455.0) == '45.5×60@455'


class TestFallbackToFirstEdge:
    """base_line 未指定(退化)時はパスの最初の辺を地廻り基準線にする。"""

    def test_spacing_gives_expected_count(self) -> None:
        # 下辺長 6000 / 間隔 1000 → 0,1000,...,6000 の 7 本
        rafters = _build(RECT, spacing=1000.0)
        assert len(rafters) == 7

    def test_rafters_origin_on_base_edge(self) -> None:
        rafters = _build(RECT, spacing=2000.0)
        # 配置点は下辺 (y=0) 上、x は 0,2000,4000,6000
        xs = sorted(r['origin'][0] for r in rafters)
        assert xs == pytest.approx([0.0, 2000.0, 4000.0, 6000.0])
        assert all(r['origin'][1] == pytest.approx(0.0) for r in rafters)

    def test_span_reaches_far_edge_no_overhang(self) -> None:
        rafters = _build(RECT, spacing=2000.0)
        # フォールバックは基準辺から屋根面側 1 方向 → span=4000, overhang=0
        for r in rafters:
            assert r['span'] == pytest.approx(4000.0)
            assert r['overhang'] == pytest.approx(0.0)
            # 棟方向(+y)への平面回転角 = 90 度
            assert r['angle'] == pytest.approx(90.0)

    def test_pitch_follows_slope(self) -> None:
        # 勾配角 = atan(寸勾配/10)。4 寸なら約 21.8 度。
        rafters = _build(RECT, slope=4.0, spacing=2000.0)
        for r in rafters:
            assert r['pitch'] == pytest.approx(_pitch(4.0))

    def test_flat_slope_has_zero_pitch(self) -> None:
        rafters = _build(RECT, slope=0.0, spacing=2000.0)
        assert all(r['pitch'] == pytest.approx(0.0) for r in rafters)

    def test_section_and_class_propagated(self) -> None:
        rafters = _build(RECT, width=45.0, height=105.0, spacing=3000.0)
        for r in rafters:
            assert r['width'] == 45.0
            assert r['height'] == 105.0
            assert r['class'] == CLASS
            assert r['label'] == '45×105@3000'

    def test_degenerate_base_line_falls_back(self) -> None:
        # 2 点が一致する base_line は退化 → 最初の辺へフォールバック
        degenerate = _build(RECT, base_line=[[10.0, 10.0], [10.0, 10.0]],
                            spacing=2000.0)
        assert degenerate == _build(RECT, base_line=None, spacing=2000.0)


class TestFreeBaseLine:
    """地廻り基準線をコントロールポイント(2 点)で内蔵直線として与える。"""

    # RECT の内側 y=1000 に水平な地廻り線。軒の出 1000(y=0 まで)、棟側 3000。
    BASE = [[0.0, 1000.0], [6000.0, 1000.0]]

    def test_span_and_overhang_from_clip(self) -> None:
        rafters = _build(RECT, base_line=self.BASE, spacing=2000.0)
        # パス幅 6000 / 間隔 2000 → x = 0,2000,4000,6000 の 4 本
        assert len(rafters) == 4
        for r in rafters:
            # 配置点=地廻り基準線上 (y=1000)
            assert r['origin'][1] == pytest.approx(1000.0)
            # 棟側(y=4000 まで 3000)が本体、軒側(y=0 まで 1000)が軒の出
            assert r['span'] == pytest.approx(3000.0)
            assert r['overhang'] == pytest.approx(1000.0)
            assert r['angle'] == pytest.approx(90.0)

    def test_ridge_side_auto_detected_regardless_of_point_order(self) -> None:
        # 始点・終点を入れ替えても棟(広い側=span)・軒先(狭い側=overhang)は同じ
        forward = _build(RECT, base_line=self.BASE, spacing=2000.0)
        reversed_line = [self.BASE[1], self.BASE[0]]
        backward = _build(RECT, base_line=reversed_line, spacing=2000.0)
        for r in forward + backward:
            assert r['span'] == pytest.approx(3000.0)     # 棟側(広い)
            assert r['overhang'] == pytest.approx(1000.0)  # 軒先(狭い)
            assert r['angle'] == pytest.approx(90.0)

    def test_short_base_line_extends_over_full_path(self) -> None:
        # 基準線がパス幅より短くても、無限直線として延長しパス幅全域に並べる。
        # 基準線は x=2000..4000 の中央 2000 幅だが、パスは x=0..6000。
        short = [[2000.0, 1000.0], [4000.0, 1000.0]]
        rafters = _build(RECT, base_line=short, spacing=2000.0)
        # 始点(x=2000)を 0 とした ±2000 の倍数 → x = 0,2000,4000,6000 の 4 本
        xs = sorted(r['origin'][0] for r in rafters)
        assert xs == pytest.approx([0.0, 2000.0, 4000.0, 6000.0])
        # 基準線の 2 端点の間(x=2000..4000)に限らず両側へ延びている
        assert min(xs) < 2000.0
        assert max(xs) > 4000.0

    def test_base_line_start_is_spacing_origin(self) -> None:
        # 間隔の起点は基準線の始点(s=0)。始点が x=500 なら格子は 500 + k*2000。
        offset = [[500.0, 1000.0], [3000.0, 1000.0]]
        rafters = _build(RECT, base_line=offset, spacing=2000.0)
        xs = sorted(r['origin'][0] for r in rafters)
        # 500 を 0 とした倍数のうち x=0..6000 に入るもの: 500,2500,4500
        assert xs == pytest.approx([500.0, 2500.0, 4500.0])

    def test_base_line_not_parallel_to_edges(self) -> None:
        # 斜めの地廻り線でも直交方向に垂木が伸びる(退化しない)
        rafters = _build(
            RECT, base_line=[[1000.0, 500.0], [5000.0, 1500.0]],
            spacing=1500.0)
        assert len(rafters) >= 1
        for r in rafters:
            assert r['span'] > 0.0


class TestTriangle:
    # 二等辺三角形の屋根投影(下辺を基準線、頂点が棟)。
    TRI = [[0.0, 0.0], [6000.0, 0.0], [3000.0, 3000.0]]

    def test_lengths_vary_with_position(self) -> None:
        rafters = _build(self.TRI, base_line=None, spacing=1000.0)
        assert len(rafters) >= 1
        # 中央(x=3000 付近)の垂木が最も長い(棟に届く)→ span が位置で変わる
        spans = [r['span'] for r in rafters]
        assert max(spans) > min(spans)


class TestDegenerate:
    def test_empty_path_returns_empty(self) -> None:
        assert _build([]) == []

    def test_two_point_path_returns_empty(self) -> None:
        assert _build([[0.0, 0.0], [1000.0, 0.0]]) == []

    def test_zero_spacing_returns_empty(self) -> None:
        assert _build(RECT, spacing=0.0) == []

    def test_negative_spacing_returns_empty(self) -> None:
        assert _build(RECT, spacing=-100.0) == []

    def test_closed_path_duplicate_endpoint_deduped(self) -> None:
        # 末尾が先頭と一致する閉じたパスでも長方形として扱う
        closed = RECT + [[0.0, 0.0]]
        assert _build(closed, spacing=2000.0) == _build(RECT, spacing=2000.0)


class TestBuildDocument:
    def test_wraps_commands_in_document(self) -> None:
        doc = build_document(
            RECT, base_line=None, slope=4.0, width=45.0, height=60.0,
            spacing=2000.0, rafter_class=CLASS, **MEMBER_PARAMS)
        assert doc['version'] == 2
        assert len(doc['rafters']) == 4

    def test_proxied_member_params_on_each_command(self) -> None:
        doc = build_document(
            RECT, base_line=None, slope=4.0, width=45.0, height=60.0,
            spacing=2000.0, rafter_class=CLASS,
            **{**MEMBER_PARAMS, 'config': 'DWB', 'material': 'SPF'})
        assert doc['rafters']
        for rafter in doc['rafters']:
            assert rafter['config'] == 'DWB'
            assert rafter['material'] == 'SPF'
