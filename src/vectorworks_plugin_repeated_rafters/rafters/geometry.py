"""垂木の水平投影線・傾きを求めるジオメトリ計算(vs 非依存)。

屋根の水平投影面(閉ポリゴン)・地廻り基準線・勾配・垂木断面・間隔から、
垂木 1 本ごとの命令(``RafterCommand``)を組み立てる。

配置モデル(ユーザー確認済み):

- **地廻り基準線は内蔵の直線**: 地廻り(軒側の高さ基準)は、屋根の水平投影面の
  辺ではなく、2 点(2 つのコントロールポイント)で与える**別途の直線**で指定する。
  軒の出があると屋根投影面の軒側の辺は軒先であって地廻りではないため、地廻りを
  辺で制御せず独立に置けるようにしている(``base_line``)。
- **基準線に直交**: 垂木は地廻り基準線に直交する向きで、基準線に沿って指定間隔で
  並ぶ。
- **基準線は無限直線**: 垂木を並べる範囲は基準線の 2 端点の間に限らない。基準線を
  無限に延長した直線とみなし、屋根の水平投影面(パス)を基準線方向へ射影した
  広がりの全域に、始点を 0 とした指定間隔の位置で垂木を並べる。各垂木は下記の
  とおり屋根投影面でクリップされる。
- **面全体・両方向**: 各垂木は地廻り基準線から棟側(高い側)と軒先側(低い側)の
  **両方向**へ伸び、屋根水平投影面でクリップした長さになる。地廻りより軒先側
  (軒の出)は基準より下がる。
- **勾配なりに傾く**: 立ち上がり = 地廻り基準線からの水平距離 × 勾配/10。
  高さ 0 の基準(データム)は地廻り基準線。棟側は正、軒先側(軒の出)は負の高さ。
  勾配は寸勾配(10 の水平に対する立ち上がり、例 4 = 4/10)。
- **棟/軒先の向きの自動判定**: 基準線の中点から屋根投影面が広く伸びる側を棟
  (高い側)、狭い側(軒の出)を軒先(低い側)として自動的に決める。ユーザーは
  コントロールポイントの向き(始点・終点の順序)を気にしなくてよい。

``base_line`` が退化(2 点が一致など)している場合は、従来どおりパスの最初の辺を
地廻り基準線とみなし、内向き(屋根面側)にだけ垂木を伸ばすフォールバックに切り替える
(コントロールポイント未設定の新規オブジェクトでも何か描けるようにするため)。

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
    確認・補正する。フォールバック(パスの辺を地廻り基準線に使う)で用いる。
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

    フォールバック(パスの辺を地廻り基準線に使う)で、辺から屋根面側へ 1 方向に
    垂木を伸ばすときに用いる。半直線に平行な辺は無視する。
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


def _line_signed_intersections(
    origin: Point, axis: Point, pts: list[Point],
) -> list[float]:
    """origin を通り axis(単位)方向の**直線**とポリゴン各辺の交点の、符号付き
    パラメータ t のリスト(交点 = origin + t*axis)。

    正の t は axis 方向、負の t は逆方向。原点自身(|t|<=_EPS)や axis に平行な
    辺は除外する。地廻り基準線から棟側・軒先側の両方向へ垂木を伸ばすため、
    半直線ではなく直線として両側の交点を集める。
    """
    ox, oy = origin
    dx, dy = axis
    n = len(pts)
    ts: list[float] = []
    for i in range(n):
        p = pts[i]
        q = pts[(i + 1) % n]
        ex = q[0] - p[0]
        ey = q[1] - p[1]
        denom = dx * (-ey) - dy * (-ex)
        if abs(denom) <= _EPS:
            continue  # 平行(または退化した辺)
        rhs_x = p[0] - ox
        rhs_y = p[1] - oy
        t = (rhs_x * (-ey) - rhs_y * (-ex)) / denom
        u = (dx * rhs_y - dy * rhs_x) / denom
        if u < -_EPS or u > 1.0 + _EPS:
            continue
        if abs(t) <= _EPS:
            continue  # 原点(基準線上)は除外
        ts.append(t)
    return ts


def _projection_range(
    origin: Point, axis: Point, pts: list[Point],
) -> tuple[float, float]:
    """pts を origin 基準・axis(単位)方向へ射影した符号付き距離の [最小, 最大]。

    地廻り基準線を無限直線とみなし、垂木を並べる範囲を屋根投影面(パス)の
    広がりで決めるために使う。origin(基準線の始点)を 0 とした軸方向の座標で、
    パス頂点が届く最小・最大位置を返す。
    """
    projs = [
        (p[0] - origin[0]) * axis[0] + (p[1] - origin[1]) * axis[1]
        for p in pts
    ]
    return min(projs), max(projs)


def _choose_up_normal(
    mid: Point, left: Point, right: Point, pts: list[Point],
) -> Point:
    """棟(高い側)を向く法線を、基準線の中点から屋根投影面が広く伸びる側で決める。

    left(基準線の進行方向左)・right(右)それぞれの向きへ屋根投影面がどこまで
    伸びるかを中点からの交点で測り、広い側を棟(=垂木が長く伸びる高い側)とする。
    狭い側が軒先(軒の出)。同程度なら left を採用して決定的にする。
    """
    ts = _line_signed_intersections(mid, left, pts)
    if not ts:
        return left
    left_ext = max((t for t in ts if t > 0.0), default=0.0)   # left 側の伸び
    right_ext = -min((t for t in ts if t < 0.0), default=0.0)  # right 側の伸び
    return left if left_ext >= right_ext else right


def make_member_id(width: float, height: float) -> str:
    """垂木の構造材 ID "{幅}×{成} - 垂木" を組み立てる(整数寸は小数点なし)。"""
    return f'{_format_mm(width)}×{_format_mm(height)} - 垂木'


def _format_mm(value: float) -> str:
    """寸法(mm)を表示用文字列にする(整数値は末尾の .0 を付けない)。"""
    return f'{value:g}'


def _resolve_base_line(
    base_line: list[list[float]] | None, pts: list[Point],
) -> tuple[Point, Point, bool]:
    """地廻り基準線の 2 端点と、フリーモードかどうかを返す。

    ``base_line`` が有効(2 点が離れている)ならそれを使う(フリーモード)。
    退化・未指定ならパスの最初の辺を基準辺に使うフォールバック(非フリーモード)。
    """
    if base_line is not None and len(base_line) >= 2:
        p1 = (float(base_line[0][0]), float(base_line[0][1]))
        p2 = (float(base_line[1][0]), float(base_line[1][1]))
        if _distance(p1, p2) > _EPS:
            return p1, p2, True
    # フォールバック: パスの最初の辺を地廻り基準線とみなす
    return pts[0], pts[1], False


def build_rafter_commands(
    path: list[list[float]],
    *,
    base_line: list[list[float]] | None,
    slope: float,
    width: float,
    height: float,
    spacing: float,
    rafter_class: str,
    profile_shape: str,
    profile_series: str,
    member_type: str,
    structural_use: str,
    axis_align: str,
    start_condition: str,
    end_condition: str,
    material: str,
) -> list[RafterCommand]:
    """屋根水平投影面と各パラメータから垂木命令のリストを組み立てる。

    Args:
        path: 屋根水平投影面の外形頂点列 [[x, y], ...](PIO のパス。閉ポリゴン)。
        base_line: 地廻り基準線の 2 端点 [[x1, y1], [x2, y2]](コントロール
            ポイント)。垂木はこの直線に直交し、直線を無限に延長した向きに沿って
            ``spacing`` 間隔で並ぶ。並ぶ範囲は 2 端点の間ではなく、屋根投影面
            (パス)を基準線方向へ射影した広がり全域。``None`` や退化した線の
            場合はパスの最初の辺を基準辺に使う。
        slope: 寸勾配(10 の水平に対する立ち上がり、例 4 = 4/10)。
        width: 垂木幅 (mm, 基準線方向の断面寸法)。
        height: 垂木成 (mm)。
        spacing: 垂木の間隔 (mm, 基準線に沿った配置間隔)。
        rafter_class: 各垂木に割り当てる作図クラス名。
        profile_shape: 軸組ツールからプロキシする断面形状 (StructuralMember の
            ``ProfileShape``。通常 ``Rectangle``)。以下 7 つと共に、ジオメトリ
            計算はこれらを解釈せず各命令へそのまま載せ、描画フェーズが対応する
            StructuralMember レコードフィールドへ転送する(構造・断面の要点のみ)。
        profile_series: 断面シリーズ (``ProfileSeries``)。
        member_type: 部材タイプ (``MemberType``)。
        structural_use: 構造用途 (``StructuralUse``)。
        axis_align: 軸の位置合わせ (``AxisAlign``)。
        start_condition: 始端条件 (``StartCondition``)。
        end_condition: 終端条件 (``EndCondition``)。
        material: 部材材質 (``MemberMaterial``。空文字は無指定)。

    Returns:
        垂木命令のリスト。頂点が 3 点未満・基準線が退化・間隔が 0 以下など
        垂木を並べられない場合は空リスト。
    """
    pts = _dedupe_polygon(path)
    if len(pts) < 3 or spacing <= _EPS:
        return []

    p1, p2, free_mode = _resolve_base_line(base_line, pts)
    base_len = _distance(p1, p2)
    if base_len <= _EPS:
        return []

    ex = (p2[0] - p1[0]) / base_len
    ey = (p2[1] - p1[1]) / base_len

    if free_mode:
        # 基準線に直交する 2 法線(進行方向の左・右)。棟側を自動判定する。
        left = (-ey, ex)
        right = (ey, -ex)
        mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        up = _choose_up_normal(mid, left, right, pts)
    else:
        # フォールバック: パスの辺の内向き(屋根面側)を棟側とする。
        up = _inward_normal(p1, p2, pts)
        if abs(up[0]) <= _EPS and abs(up[1]) <= _EPS:
            return []

    member_id = make_member_id(width, height)
    commands: list[RafterCommand] = []

    # 地廻り基準線を無限直線とみなし、垂木を並べる範囲は屋根投影面(パス)を
    # 基準線方向へ射影した広がりで決める(基準線の 2 端点の間だけに限らない)。
    # 基準線の始点(p1)を 0 とし、s = k*spacing (両向きの整数 k)の位置に並べる。
    # 各位置の垂木は下の交点計算で屋根投影面によりクリップされる。
    s_min, s_max = _projection_range(p1, (ex, ey), pts)
    k_min = int(math.ceil(s_min / spacing - _EPS))
    k_max = int(math.floor(s_max / spacing + _EPS))
    for k in range(k_min, k_max + 1):
        s = k * spacing
        origin = (p1[0] + ex * s, p1[1] + ey * s)
        if free_mode:
            # 棟側(正)・軒先側(負)の両方向へ屋根投影面までクリップする。
            ts = _line_signed_intersections(origin, up, pts)
            if len(ts) < 2:
                continue
            t_min = min(ts)  # 最も軒先側(低い側)
            t_max = max(ts)  # 最も棟側(高い側)
        else:
            # フォールバック: 基準辺(t=0)から屋根面側の最遠縁まで 1 方向。
            t_far = _ray_far_intersection(origin, up, pts)
            if t_far is None or t_far <= _EPS:
                continue
            t_min = 0.0
            t_max = t_far
        if t_max - t_min <= _EPS:
            continue
        start = (origin[0] + up[0] * t_min, origin[1] + up[1] * t_min)
        end = (origin[0] + up[0] * t_max, origin[1] + up[1] * t_max)
        # 立ち上がり = 地廻り基準線(t=0)からの水平距離 × 勾配/10。
        # 高さ 0 の基準は地廻り基準線。軒先側(t<0)は負になる。
        commands.append({
            'class': rafter_class,
            'member_id': member_id,
            'start': [start[0], start[1]],
            'end': [end[0], end[1]],
            'width': width,
            'height': height,
            'elevation': t_min * slope / 10.0,
            'end_elevation': t_max * slope / 10.0,
            # 軸組ツール(StructuralMember)からプロキシする値。ジオメトリ計算は
            # 解釈せず、そのまま各命令へ載せる(描画フェーズが SetRField で転送)。
            'profile_shape': profile_shape,
            'profile_series': profile_series,
            'member_type': member_type,
            'structural_use': structural_use,
            'axis_align': axis_align,
            'start_condition': start_condition,
            'end_condition': end_condition,
            'material': material,
        })
    return commands
