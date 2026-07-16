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
水平投影面)とパラメータ(勾配・基準辺・断面・間隔・クラス)を vs から読み取り、
2 フェーズを通して垂木を描く。

**VectorWorks 側のプラグイン登録**: このパッケージが動くには、VectorWorks の
プラグインマネージャで**パスプラグインオブジェクト**を下記の名前・パラメータで
登録し、そのオブジェクトスクリプトに ``main.py`` の内容を貼り付ける必要がある
(名前・パラメータ名はここの定数と一致させること):

- プラグイン名(レコード名): ``垂木群`` (= ``PLUGIN_NAME``)
- オブジェクトタイプ: パス(Path)。パスが屋根の水平投影面になる。
- パラメータ(いずれもフィールド名 = 下記 ``PARAM_*``):
  - ``Slope``      実数  勾配(寸勾配、10 の水平に対する立ち上がり)
  - ``BaseEdge``   整数  地廻り基準線とするパスの辺番号(1 始まり)
  - ``Width``      実数  垂木幅 (mm)
  - ``Height``     実数  垂木成 (mm)
  - ``Spacing``    実数  垂木の間隔 (mm)
  - ``RafterClass`` 文字 垂木に割り当てる作図クラス名
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
PARAM_BASE_EDGE = 'BaseEdge'
PARAM_WIDTH = 'Width'
PARAM_HEIGHT = 'Height'
PARAM_SPACING = 'Spacing'
PARAM_CLASS = 'RafterClass'

# パラメータ未設定時の既定値。
DEFAULT_SLOPE = 4.0          # 4 寸勾配
DEFAULT_BASE_EDGE = 1        # パスの最初の辺
DEFAULT_WIDTH = 45.0         # 垂木幅 45mm
DEFAULT_HEIGHT = 60.0        # 垂木成 60mm
DEFAULT_SPACING = 455.0      # 1.5 尺 ≒ 455mm
DEFAULT_CLASS = '04構造-02木造-05小屋組-05垂木'


def _to_float(value: Any, default: float) -> float:
    """vs のパラメータ値(文字列/実数)を float にする(空/不正は default)。"""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    """vs のパラメータ値を int にする(空/不正は default)。"""
    if value is None or value == '':
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


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


def _read_parameters(vs: Any, obj: Any) -> dict[str, Any]:
    """PIO のパラメータ(勾配・基準辺・断面・間隔・クラス)を読み取る。"""
    rafter_class = vs.GetRField(obj, PLUGIN_NAME, PARAM_CLASS)
    if not rafter_class:
        rafter_class = DEFAULT_CLASS
    return {
        'base_edge': _to_int(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_BASE_EDGE), DEFAULT_BASE_EDGE),
        'slope': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_SLOPE), DEFAULT_SLOPE),
        'width': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_WIDTH), DEFAULT_WIDTH),
        'height': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_HEIGHT), DEFAULT_HEIGHT),
        'spacing': _to_float(
            vs.GetRField(obj, PLUGIN_NAME, PARAM_SPACING), DEFAULT_SPACING),
        'rafter_class': rafter_class,
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

    ok, obj, _rec, _wall = vs.GetCustomObjectInfo()
    if not ok or obj == vs.Handle(0):
        return

    path = _read_path_points(vs, obj)
    params = _read_parameters(vs, obj)

    document = build_document(path, **params)
    # JSON 文字列を経由して受け渡すことで、命令セットが常に直列化可能
    # (= vs のオブジェクトを含まない)ことを保証する。
    document = json.loads(json.dumps(document))

    execute_document(document)
