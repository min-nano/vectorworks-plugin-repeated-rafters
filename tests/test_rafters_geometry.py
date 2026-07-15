"""ジオメトリ計算フェーズ (rafters) のテスト。vs 非依存。"""
from __future__ import annotations

import pytest

from vectorworks_plugin_repeated_rafters.rafters import build_document
from vectorworks_plugin_repeated_rafters.rafters.geometry import (
    build_rafter_commands,
    make_member_id,
)

# 反時計回りの長方形(幅 6000 × 奥行 4000)。辺 1 = 下辺 (0,0)->(6000,0)。
RECT = [[0.0, 0.0], [6000.0, 0.0], [6000.0, 4000.0], [0.0, 4000.0]]

CLASS = '04構造-02木造-05小屋組-05垂木'


def _build(path: list[list[float]], **kwargs: object) -> list:
    params: dict = {
        'base_edge': 1,
        'slope': 4.0,
        'width': 45.0,
        'height': 60.0,
        'spacing': 1000.0,
        'rafter_class': CLASS,
    }
    params.update(kwargs)
    return build_rafter_commands(path, **params)


class TestMakeMemberId:
    def test_integer_dimensions_have_no_decimal(self) -> None:
        assert make_member_id(45.0, 60.0) == '45×60 - 垂木'

    def test_non_integer_dimensions_kept(self) -> None:
        assert make_member_id(45.5, 60.0) == '45.5×60 - 垂木'


class TestRectangle:
    def test_spacing_gives_expected_count(self) -> None:
        # 下辺長 6000 / 間隔 1000 → 0,1000,...,6000 の 7 本
        rafters = _build(RECT, spacing=1000.0)
        assert len(rafters) == 7

    def test_rafters_start_on_base_edge(self) -> None:
        rafters = _build(RECT, spacing=2000.0)
        # 始端は下辺 (y=0) 上、x は 0,2000,4000,6000
        xs = sorted(r['start'][0] for r in rafters)
        assert xs == pytest.approx([0.0, 2000.0, 4000.0, 6000.0])
        assert all(r['start'][1] == pytest.approx(0.0) for r in rafters)

    def test_rafters_span_to_far_edge(self) -> None:
        rafters = _build(RECT, spacing=2000.0)
        # 終端は上辺 (y=4000) 上、x は始端と同じ(基準線に直交)
        for r in rafters:
            assert r['end'][0] == pytest.approx(r['start'][0])
            assert r['end'][1] == pytest.approx(4000.0)

    def test_rise_follows_slope(self) -> None:
        # 立ち上がり = 水平投影長(4000) × 勾配(4)/10 = 1600
        rafters = _build(RECT, slope=4.0, spacing=2000.0)
        for r in rafters:
            assert r['elevation'] == pytest.approx(0.0)
            assert r['end_elevation'] == pytest.approx(1600.0)

    def test_flat_slope_has_no_rise(self) -> None:
        rafters = _build(RECT, slope=0.0, spacing=2000.0)
        assert all(r['end_elevation'] == pytest.approx(0.0) for r in rafters)

    def test_section_and_class_propagated(self) -> None:
        rafters = _build(RECT, width=45.0, height=105.0, spacing=3000.0)
        for r in rafters:
            assert r['width'] == 45.0
            assert r['height'] == 105.0
            assert r['class'] == CLASS
            assert r['member_id'] == '45×105 - 垂木'

    def test_base_edge_selects_perpendicular_direction(self) -> None:
        # 辺 2 = 右辺 (6000,0)->(6000,4000)。垂木は左向き、長さ 6000。
        rafters = _build(RECT, base_edge=2, spacing=1000.0)
        # 右辺長 4000 / 間隔 1000 → 5 本
        assert len(rafters) == 5
        for r in rafters:
            assert r['start'][0] == pytest.approx(6000.0)
            assert r['end'][0] == pytest.approx(0.0)
            # 立ち上がり = 6000 × 4/10 = 2400
            assert r['end_elevation'] == pytest.approx(2400.0)

    def test_base_edge_wraps_modulo_vertex_count(self) -> None:
        # 辺 5 は頂点 4 つの長方形では辺 1 に巻き込まれる(5-1=4, 4%4=0)
        wrapped = _build(RECT, base_edge=5, spacing=1000.0)
        first = _build(RECT, base_edge=1, spacing=1000.0)
        assert wrapped == first


class TestTriangle:
    # 二等辺三角形の屋根投影(下辺を基準線、頂点が棟)。
    TRI = [[0.0, 0.0], [6000.0, 0.0], [3000.0, 3000.0]]

    def test_lengths_vary_with_position(self) -> None:
        rafters = _build(self.TRI, base_edge=1, spacing=1000.0)
        assert len(rafters) >= 1
        # 中央(x=3000 付近)の垂木が最も長い(棟に届く)
        rises = [r['end_elevation'] for r in rafters]
        # 立ち上がりは位置によって異なる(全て同一でない)
        assert max(rises) > min(rises)


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
            RECT, base_edge=1, slope=4.0, width=45.0, height=60.0,
            spacing=2000.0, rafter_class=CLASS)
        assert doc['version'] == 1
        assert len(doc['rafters']) == 4
