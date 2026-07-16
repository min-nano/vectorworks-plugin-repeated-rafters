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
        'base_line': None,   # 既定はフォールバック(パスの最初の辺)
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


class TestFallbackToFirstEdge:
    """base_line 未指定(退化)時はパスの最初の辺を地廻り基準線にする。"""

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
        # 立ち上がり = 水平投影長(4000) × 勾配(4)/10 = 1600。基準辺が高さ 0。
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

    def test_degenerate_base_line_falls_back(self) -> None:
        # 2 点が一致する base_line は退化 → 最初の辺へフォールバック
        degenerate = _build(RECT, base_line=[[10.0, 10.0], [10.0, 10.0]],
                            spacing=2000.0)
        assert degenerate == _build(RECT, base_line=None, spacing=2000.0)


class TestFreeBaseLine:
    """地廻り基準線をコントロールポイント(2 点)で内蔵直線として与える。"""

    # RECT の内側 y=1000 に水平な地廻り線。軒の出 1000(y=0 まで)、棟側 3000。
    BASE = [[0.0, 1000.0], [6000.0, 1000.0]]

    def test_spans_both_directions_from_base_line(self) -> None:
        rafters = _build(RECT, base_line=self.BASE, spacing=2000.0)
        # パス幅 6000 / 間隔 2000 → x = 0,2000,4000,6000 の 4 本
        assert len(rafters) == 4
        for r in rafters:
            # 始端=軒先側(y=0、軒の出の先)、終端=棟側(y=4000)
            assert r['start'][1] == pytest.approx(0.0)
            assert r['end'][1] == pytest.approx(4000.0)
            # 基準線に直交(x 一定)
            assert r['start'][0] == pytest.approx(r['end'][0])

    def test_datum_at_base_line_with_signed_elevation(self) -> None:
        rafters = _build(RECT, base_line=self.BASE, slope=4.0, spacing=2000.0)
        for r in rafters:
            # 軒先側(基準線から 1000 下)は負: -1000 × 4/10 = -400
            assert r['elevation'] == pytest.approx(-400.0)
            # 棟側(基準線から 3000 上): 3000 × 4/10 = 1200
            assert r['end_elevation'] == pytest.approx(1200.0)
            # 全長の立ち上がり = 4000 × 4/10 = 1600
            assert r['end_elevation'] - r['elevation'] == pytest.approx(1600.0)

    def test_ridge_side_auto_detected_regardless_of_point_order(self) -> None:
        # 始点・終点を入れ替えても棟(広い側)・軒先(狭い側)は同じに決まる
        forward = _build(RECT, base_line=self.BASE, spacing=2000.0)
        reversed_line = [self.BASE[1], self.BASE[0]]
        backward = _build(RECT, base_line=reversed_line, spacing=2000.0)
        f_ends = sorted((r['start'][1], r['end'][1]) for r in forward)
        b_ends = sorted((r['start'][1], r['end'][1]) for r in backward)
        assert f_ends == pytest.approx(b_ends)
        for r in forward + backward:
            assert r['start'][1] == pytest.approx(0.0)    # 軒先(低い)
            assert r['end'][1] == pytest.approx(4000.0)   # 棟(高い)

    def test_short_base_line_extends_over_full_path(self) -> None:
        # 基準線がパス幅より短くても、無限直線として延長しパス幅全域に並べる。
        # 基準線は x=2000..4000 の中央 2000 幅だが、パスは x=0..6000。
        short = [[2000.0, 1000.0], [4000.0, 1000.0]]
        rafters = _build(RECT, base_line=short, spacing=2000.0)
        # 始点(x=2000)を 0 とした ±2000 の倍数 → x = 0,2000,4000,6000 の 4 本
        xs = sorted(r['start'][0] for r in rafters)
        assert xs == pytest.approx([0.0, 2000.0, 4000.0, 6000.0])
        # 基準線の 2 端点の間(x=2000..4000)に限らず両側へ延びている
        assert min(xs) < 2000.0
        assert max(xs) > 4000.0

    def test_base_line_start_is_spacing_origin(self) -> None:
        # 間隔の起点は基準線の始点(s=0)。始点が x=500 なら格子は 500 + k*2000。
        offset = [[500.0, 1000.0], [3000.0, 1000.0]]
        rafters = _build(RECT, base_line=offset, spacing=2000.0)
        xs = sorted(r['start'][0] for r in rafters)
        # 500 を 0 とした倍数のうち x=0..6000 に入るもの: 500,2500,4500
        assert xs == pytest.approx([500.0, 2500.0, 4500.0])

    def test_base_line_not_parallel_to_edges(self) -> None:
        # 斜めの地廻り線でも直交方向に垂木が伸びる(退化しない)
        rafters = _build(
            RECT, base_line=[[1000.0, 500.0], [5000.0, 1500.0]],
            spacing=1500.0)
        assert len(rafters) >= 1
        for r in rafters:
            assert r['start'] != r['end']


class TestTriangle:
    # 二等辺三角形の屋根投影(下辺を基準線、頂点が棟)。
    TRI = [[0.0, 0.0], [6000.0, 0.0], [3000.0, 3000.0]]

    def test_lengths_vary_with_position(self) -> None:
        rafters = _build(self.TRI, base_line=None, spacing=1000.0)
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
            RECT, base_line=None, slope=4.0, width=45.0, height=60.0,
            spacing=2000.0, rafter_class=CLASS)
        assert doc['version'] == 1
        assert len(doc['rafters']) == 4
