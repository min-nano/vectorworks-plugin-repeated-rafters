"""屋根面に垂木を指定間隔で並べる VectorWorks プラグインオブジェクト(PIO)。

姉妹プロジェクト vectorworks_plugin_import_ifc_homeskz と同じ「2 フェーズ分離
+ JSON 命令セット」の設計を踏襲している:

1. ジオメトリ計算フェーズ (``rafters`` パッケージ, vs 非依存)
   屋根の水平投影面(PIO のパス)と各パラメータから、描くべき垂木を
   JSON 直列化可能な命令セットとして組み立てる。通常の Python 環境で検証できる。
2. 描画フェーズ (``vw`` パッケージ, vs 依存)
   命令セットに従って構造材ツール(軸組ツール)で垂木を描く。

このモジュールの ``run()`` は **PIO のオブジェクトスクリプト本体**で、VectorWorks が
オブジェクトの再生成(リセット)のたびに呼び出す。オブジェクトのパス(=屋根の
水平投影面)とパラメータ(勾配・地廻り基準線・断面・間隔・クラス)を vs から読み取り、
2 フェーズを通して垂木を描く。

**VectorWorks 側のプラグイン登録**: このパッケージが動くには、VectorWorks の
プラグインマネージャで**パスプラグインオブジェクト**を下記の名前・パラメータで
登録し、そのオブジェクトスクリプトに ``main.py`` の内容を貼り付ける必要がある
(名前・パラメータ名はここの定数と一致させること):

- プラグイン名(レコード名): ``垂木群`` (= ``PLUGIN_NAME``)
- オブジェクトタイプ: パス(Path)。パスが屋根の水平投影面になる。
- パラメータ:
  - ``Slope``      実数  勾配(寸勾配、10 の水平に対する立ち上がり)
  - 1 個目のコントロールポイント  地廻り基準線の一端
    (フィールド名は任意。座標は ``ControlPoint01X`` / ``ControlPoint01Y``)
  - 2 個目のコントロールポイント  地廻り基準線の他端
    (フィールド名は任意。座標は ``ControlPoint02X`` / ``ControlPoint02Y``)
  - ``Width``      実数  垂木幅 (mm)
  - ``Height``     実数  垂木成 (mm)
  - ``Spacing``    実数  垂木の間隔 (mm)
  - ``RafterClass`` 文字 垂木に割り当てる作図クラス名
  - 軸組ツール(StructuralMember)から**プロキシ**するパラメータ(構造・断面の
    要点のみ。ここで読み取った値をそのまま各垂木の同名レコードフィールドへ転送):
    - ``ProfileShape``   文字 断面形状(既定 ``Rectangle``)
    - ``ProfileSeries``  文字 断面シリーズ(既定 ``AISC (Inch)``)
    - ``MemberType``     文字 部材タイプ(既定 ``2``)
    - ``StructuralUse``  文字 構造用途(既定 ``1``)
    - ``AxisAlign``      文字 軸の位置合わせ(既定 ``1``)
    - ``StartCondition`` 文字 始端条件(既定 ``3``)
    - ``EndCondition``   文字 終端条件(既定 ``3``)
    - ``MemberMaterial`` 文字 部材材質(既定は空=無指定)

軒の出があると屋根の水平投影面の軒側の辺は軒先であって地廻りではないため、地廻り
基準線はパスの辺ではなく **2 つのコントロールポイントで与える内蔵の直線**で指定
する。垂木はこの直線に直交し、直線に沿って ``Spacing`` 間隔で並び、地廻りから
棟側・軒先側の両方向へ屋根投影面までクリップして伸びる(高さ 0 の基準は地廻り線。
軒の出側は負の高さ)。棟/軒先の向きは自動判定するため、2 点の順序は問わない。
コントロールポイントが未設定(2 点が一致)なら、パスの最初の辺を地廻り基準線と
みなすフォールバックで描く。

**コントロールポイントのフィールド名(``BaseStart`` 等)は座標の読み取りには
使えない**。VectorWorks はコントロールポイントの「パラメータの名前(ユニバーサル
名)」を ``ControlPoint01`` / ``ControlPoint02`` … と自動採番で固定し、座標は
その名前 + ``X`` / ``Y`` (``ControlPoint01X`` 等)で ``GetRField`` から読む
(作成順に 01, 02 が割り当たる)。この座標とパス頂点(``GetPolylineVertex``)が
同一座標系で読めることは VectorWorks 上で確認する。
"""
from __future__ import annotations

from typing import Any

from .document import validate_document
from .rafters import build_document

__all__ = ['build_document', 'run', 'validate_document']

# PIO のプラグイン名(= GetRField / SetRField のレコード名)。VectorWorks の
# プラグイン登録名と一致させること。
PLUGIN_NAME = '垂木群'

# パラメータ(レコードフィールド)名。VectorWorks のプラグイン登録と一致させる。
PARAM_SLOPE = 'Slope'
PARAM_WIDTH = 'Width'
PARAM_HEIGHT = 'Height'
PARAM_SPACING = 'Spacing'
PARAM_CLASS = 'RafterClass'
# 軸組ツール(StructuralMember)で設定するパラメータのプロキシ。ここで読み取った
# 値をそのまま各垂木(StructuralMember)の同名レコードフィールドへ転送する
# (構造・断面の要点のみ。表示や Cover 等は VectorWorks の既定に委ねる)。
# PIO のパラメータ(レコードフィールド)名は転送先と同名にして対応を明確にする。
PARAM_PROFILE_SHAPE = 'ProfileShape'
PARAM_PROFILE_SERIES = 'ProfileSeries'
PARAM_MEMBER_TYPE = 'MemberType'
PARAM_STRUCTURAL_USE = 'StructuralUse'
PARAM_AXIS_ALIGN = 'AxisAlign'
PARAM_START_CONDITION = 'StartCondition'
PARAM_END_CONDITION = 'EndCondition'
PARAM_MATERIAL = 'MemberMaterial'
# 地廻り基準線のコントロールポイント。VectorWorks はコントロールポイントの
# ユニバーサル名を ControlPoint01/02... と自動採番で固定し(フィールド名を
# 変えても座標の読み取りには使えない)、座標はその名前 + X/Y のフィールドで
# 保持する。作成順に 01, 02 が割り当たる(この PIO では 2 点で地廻り線を成す)。
PARAM_BASE_START_X = 'ControlPoint01X'
PARAM_BASE_START_Y = 'ControlPoint01Y'
PARAM_BASE_END_X = 'ControlPoint02X'
PARAM_BASE_END_Y = 'ControlPoint02Y'

# パラメータ未設定時の既定値。
DEFAULT_SLOPE = 4.0          # 4 寸勾配
DEFAULT_WIDTH = 45.0         # 垂木幅 45mm
DEFAULT_HEIGHT = 60.0        # 垂木成 60mm
DEFAULT_SPACING = 455.0      # 1.5 尺 ≒ 455mm
DEFAULT_CLASS = '04構造-02木造-05小屋組-05垂木'
# 軸組ツールからプロキシするパラメータの既定値(空欄時に使う)。
DEFAULT_PROFILE_SHAPE = 'Rectangle'    # 矩形断面
DEFAULT_PROFILE_SERIES = 'AISC (Inch)'
DEFAULT_MEMBER_TYPE = '2'
DEFAULT_STRUCTURAL_USE = '1'
DEFAULT_AXIS_ALIGN = '1'
DEFAULT_START_CONDITION = '3'
DEFAULT_END_CONDITION = '3'
DEFAULT_MATERIAL = ''                  # 無指定(材質を割り当てない)


def _to_float(value: Any, default: float) -> float:
    """vs のパラメータ値(文字列/実数)を float にする(空/不正は default)。"""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_str(vs: Any, obj: Any, field: str, default: str) -> str:
    """vs のパラメータ値を文字列で読む(空欄は default)。

    軸組ツール(StructuralMember)からプロキシする文字列パラメータを読むために
    使う。``GetRField`` は未設定/空欄で ``''`` を返すため、その場合は既定値に
    落とす(明示的に空にしたい ``MemberMaterial`` は既定が ``''`` なので影響なし)。
    """
    value = vs.GetRField(obj, PLUGIN_NAME, field)
    if value is None or value == '':
        return default
    return str(value)


def _read_path_points(vs: Any, obj: Any) -> list[list[float]]:
    """PIO のパス(屋根の水平投影面)の頂点列 [[x, y], ...] を読み取る。

    ``GetCustomObjectPath`` でパス図形のハンドルを得て、頂点を 1 始まりで走査する
    (VectorWorks の頂点番号は 1 始まり)。パスが無い場合は空リストを返す。
    """
    path_h = vs.GetCustomObjectPath(obj)
    if path_h == vs.Handle(0):
        return []
    count = vs.GetVertNum(path_h)
    points: list[list[float]] = []
    for i in range(1, count + 1):
        vertex = vs.GetPolylineVertex(path_h, i)
        # GetPolylineVertex は (point, vertexType, arcRadius) を返す。
        point = vertex[0] if isinstance(vertex, (tuple, list)) else vertex
        points.append([float(point[0]), float(point[1])])
    return points


def _read_base_line(vs: Any, obj: Any) -> list[list[float]]:
    """地廻り基準線の 2 端点 [[x1, y1], [x2, y2]] をコントロールポイントから読む。

    VectorWorks はコントロールポイントの座標を、ユニバーサル名 ControlPoint01/02 の
    末尾に X/Y を付けたフィールドで保持する(フィールド名ではなくこの名前で読む)。
    2 点が一致(未設定など)する場合でもそのまま返し、退化の扱い(パスの最初の辺へ
    のフォールバック)はジオメトリ計算フェーズに委ねる。
    """
    return [
        [
            _to_float(vs.GetRField(obj, PLUGIN_NAME, PARAM_BASE_START_X), 0.0),
            _to_float(vs.GetRField(obj, PLUGIN_NAME, PARAM_BASE_START_Y), 0.0),
        ],
        [
            _to_float(vs.GetRField(obj, PLUGIN_NAME, PARAM_BASE_END_X), 0.0),
            _to_float(vs.GetRField(obj, PLUGIN_NAME, PARAM_BASE_END_Y), 0.0),
        ],
    ]


def _read_parameters(vs: Any, obj: Any) -> dict[str, Any]:
    """PIO のパラメータ(勾配・地廻り基準線・断面・間隔・クラス)を読み取る。"""
    rafter_class = vs.GetRField(obj, PLUGIN_NAME, PARAM_CLASS)
    if not rafter_class:
        rafter_class = DEFAULT_CLASS
    return {
        'base_line': _read_base_line(vs, obj),
        'slope': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_SLOPE), DEFAULT_SLOPE),
        'width': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_WIDTH), DEFAULT_WIDTH),
        'height': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_HEIGHT), DEFAULT_HEIGHT),
        'spacing': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_SPACING), DEFAULT_SPACING),
        'rafter_class': rafter_class,
        # 軸組ツール(StructuralMember)からプロキシするパラメータ。
        'profile_shape': _read_str(
            vs, obj, PARAM_PROFILE_SHAPE, DEFAULT_PROFILE_SHAPE),
        'profile_series': _read_str(
            vs, obj, PARAM_PROFILE_SERIES, DEFAULT_PROFILE_SERIES),
        'member_type': _read_str(
            vs, obj, PARAM_MEMBER_TYPE, DEFAULT_MEMBER_TYPE),
        'structural_use': _read_str(
            vs, obj, PARAM_STRUCTURAL_USE, DEFAULT_STRUCTURAL_USE),
        'axis_align': _read_str(
            vs, obj, PARAM_AXIS_ALIGN, DEFAULT_AXIS_ALIGN),
        'start_condition': _read_str(
            vs, obj, PARAM_START_CONDITION, DEFAULT_START_CONDITION),
        'end_condition': _read_str(
            vs, obj, PARAM_END_CONDITION, DEFAULT_END_CONDITION),
        'material': _read_str(vs, obj, PARAM_MATERIAL, DEFAULT_MATERIAL),
    }


def run() -> None:
    """PIO のオブジェクトスクリプト本体。

    VectorWorks がオブジェクトの再生成(リセット)のたびに呼び出す。オブジェクトの
    パス(屋根の水平投影面)とパラメータを読み取り、ジオメトリ計算フェーズで垂木
    命令を組み立て、JSON を経由して直列化可能性を保証してから、描画フェーズで
    構造材ツールにより垂木を描く。
    """
    # vs に依存するモジュールは VectorWorks 上での実行時のみ読み込む
    # (これにより rafters パッケージ = 計算フェーズは通常の Python でも使える)。
    import json

    import vs

    from .vw import execute_document

    # GetCustomObjectInfo は 5 値 (成否, オブジェクト名, オブジェクトハンドル,
    # レコードハンドル, 壁ハンドル) を返す。オブジェクトハンドルは 3 番目。
    ok, _name, obj, _rec, _wall = vs.GetCustomObjectInfo()
    if not ok or obj == vs.Handle(0):
        return

    path = _read_path_points(vs, obj)
    params = _read_parameters(vs, obj)

    document = build_document(path, **params)
    # JSON 文字列を経由して受け渡すことで、命令セットが常に直列化可能
    # (= vs のオブジェクトを含まない)ことを保証する。
    document = json.loads(json.dumps(document))

    execute_document(document)
