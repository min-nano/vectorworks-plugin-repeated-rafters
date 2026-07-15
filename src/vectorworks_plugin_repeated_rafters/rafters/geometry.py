"""垂木の水平投影線・傾きを求めるジオメトリ計算(vs 非依存)。

屋根の水平投影面(閉ポリゴン)・地廻り基準線(投影面の 1 辺)・勾配・
垂木断面・間隔から、垂木 1 本ごとの命令(``RafterCommand``)を組み立てる。

配置モデル(ユーザー確認済み):

- **基準線に直交**: 垂木は地廻り基準線(=軒側の辺)に直交する向きで、
  基準線に沿って指定間隔で並ぶ。
- **面全体**: 各垂木は基準線(軒=低い側)から屋根水平投影面の反対側の縁
  (棟=高い側)まで、水平投影面でクリップした長さで伸びる。
- **勾配なりに傾く**: 立ち上がり = 基準線からの水平距離 × 勾配/10。
  勾配は寸勾配(10 の水平に対する立ち上がり、例 4 = 4/10)。

計算はエンティティの列挙順・浮動小数の許容誤差に対して決定的。
"""
from __future__ import annotations

import math

from ..document import RafterCommand

Point = tuple[float, float]

# 幾何計算の許容誤差 (mm)。頂点の重複除去・交点判定などに使う。
_EPS = 1e-6


def _dedupe_polygon(path: list[list[float]]) -> list[Point]:
    """パス頂点列を閉ポリゴンの頂点列(連続重複・終端の閉じ重複を除去)にする。

    VectorWorks のパスは閉じている場合に始点と終点が一致することがあるため、
    連続する重複点と、末尾が先頭と一致する重複を取り除く。
    """
    pts: list[Point] = []
    for raw in path:
        p = (float(raw[0]), float(raw[1]))
        if pts and _distance(pts[-1], p) <= _EPS:
            continue
        pts.append(p)
    # 末尾が先頭と一致するなら閉じ重複を除去する
    if len(pts) >= 2 and _distance(pts[0], pts[-1]) <= _EPS:
        pts.pop()
    return pts


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _polygon_signed_area(pts: list[Point]) -> float:
    """ポリゴンの符号付き面積(反時計回りが正)。"""
    area = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _point_in_polygon(pt: Point, pts: list[Point]) -> bool:
    """点がポリゴン内部にあるか(レイキャスティング)。境界上は概ね内部扱い。"""
    x, y = pt
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _inward_normal(a: Point, b: Point, pts: list[Point]) -> Point:
    """辺 a→b の、ポリゴン内部を向く単位法線ベクトル。

    符号付き面積(巻き方向)から内向き法線を決める。反時計回り(面積>0)の
    ポリゴンでは進行方向 a→b の左が内側。中点を少しずらした点の内外判定で
    確認・補正する。
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy)
    if length <= _EPS:
        return (0.0, 0.0)
    ux, uy = dx / length, dy / length
    # 反時計回りポリゴンの内向き法線は進行方向の左 = (-uy, ux)
    left = (-uy, ux)
    if _polygon_signed_area(pts) < 0:
        left = (uy, -ux)
    # 中点から法線方向へわずかにずらした点が内部かで最終確認する
    mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    probe = (mid[0] + left[0] * 10.0 * _EPS, mid[1] + left[1] * 10.0 * _EPS)
    if not _point_in_polygon(probe, pts):
        left = (-left[0], -left[1])
    return left


def _ray_far_intersection(
    origin: Point, direction: Point, pts: list[Point],
) -> float | None:
    """origin から direction(単位)へ伸ばした半直線と、ポリゴン各辺との交点の
    うち最も遠いもの(t>_EPS の最大 t)を返す。交わらなければ None。

    面全体を貫くため、最も遠い交点(棟側の縁)までを垂木の長さにする(凸形状の
    屋根面では入口=基準線・出口=1 点で、その 1 点が返る)。半直線に平行な辺は
    交わらないものとして無視する。
    """
    ox, oy = origin
    dx, dy = direction
    n = len(pts)
    best: float | None = None
    for i in range(n):
        p = pts[i]
        q = pts[(i + 1) % n]
        ex = q[0] - p[0]
        ey = q[1] - p[1]
        # origin + t*d = p + u*e を解く
        denom = dx * (-ey) - dy * (-ex)
        if abs(denom) <= _EPS:
            continue  # 平行(または退化した辺)
        rhs_x = p[0] - ox
        rhs_y = p[1] - oy
        t = (rhs_x * (-ey) - rhs_y * (-ex)) / denom
        u = (dx * rhs_y - dy * rhs_x) / denom
        if t <= _EPS:
            continue
        if u < -_EPS or u > 1.0 + _EPS:
            continue
        if best is None or t > best:
            best = t
    return best


def make_member_id(width: float, height: float) -> str:
    """垂木の構造材 ID "{幅}×{成} - 垂木" を組み立てる(整数寸は小数点なし)。"""
    return f'{_format_mm(width)}×{_format_mm(height)} - 垂木'


def _format_mm(value: float) -> str:
    """寸法(mm)を表示用文字列にする(整数値は末尾の .0 を付けない)。"""
    return f'{value:g}'


def build_rafter_commands(
    path: list[list[float]],
    *,
    base_edge: int,
    slope: float,
    width: float,
    height: float,
    spacing: float,
    rafter_class: str,
) -> list[RafterCommand]:
    """屋根水平投影面と各パラメータから垂木命令のリストを組み立てる。

    Args:
        path: 屋根水平投影面の外形頂点列 [[x, y], ...](PIO のパス。閉ポリゴン)。
        base_edge: 地廻り基準線とする辺の番号(1 始まり)。辺 k は頂点 k と
            頂点 k+1 を結ぶ。頂点数で剰余を取るため範囲外でも巻き込む。
        slope: 寸勾配(10 の水平に対する立ち上がり、例 4 = 4/10)。
        width: 垂木幅 (mm, 基準線方向の断面寸法)。
        height: 垂木成 (mm)。
        spacing: 垂木の間隔 (mm, 基準線に沿った配置間隔)。
        rafter_class: 各垂木に割り当てる作図クラス名。

    Returns:
        垂木命令のリスト。頂点が 3 点未満・基準辺が退化・間隔が 0 以下など
        垂木を並べられない場合は空リスト。
    """
    pts = _dedupe_polygon(path)
    if len(pts) < 3 or spacing <= _EPS:
        return []

    n = len(pts)
    i0 = base_edge - 1
    # 1 始まりの辺番号を 0 始まりに直し、頂点数で巻き込む(範囲外・負値も許容)
    i0 = ((i0 % n) + n) % n
    a = pts[i0]
    b = pts[(i0 + 1) % n]
    base_len = _distance(a, b)
    if base_len <= _EPS:
        return []

    ex = (b[0] - a[0]) / base_len
    ey = (b[1] - a[1]) / base_len
    nx, ny = _inward_normal(a, b, pts)
    if abs(nx) <= _EPS and abs(ny) <= _EPS:
        return []

    member_id = make_member_id(width, height)
    commands: list[RafterCommand] = []

    # 基準線に沿って 0, spacing, 2*spacing, ... の位置に垂木を並べる
    # (両端の角を含む。base_len を超えない範囲)。
    steps = int(math.floor(base_len / spacing + _EPS)) + 1
    for k in range(steps):
        s = min(k * spacing, base_len)
        origin = (a[0] + ex * s, a[1] + ey * s)
        t_max = _ray_far_intersection(origin, (nx, ny), pts)
        if t_max is None or t_max <= _EPS:
            continue
        end = (origin[0] + nx * t_max, origin[1] + ny * t_max)
        rise = t_max * slope / 10.0
        commands.append({
            'class': rafter_class,
            'member_id': member_id,
            'start': [origin[0], origin[1]],
            'end': [end[0], end[1]],
            'width': width,
            'height': height,
            'elevation': 0.0,
            'end_elevation': rise,
        })
    return commands
