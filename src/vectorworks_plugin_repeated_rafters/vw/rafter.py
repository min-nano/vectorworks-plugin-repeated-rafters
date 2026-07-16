"""rafter 命令の描画。VectorWorks 構造材ツール(軸組ツール)で垂木を配置する。

姉妹プロジェクト vectorworks_plugin_import_ifc_homeskz の ``vw/member.py`` と
同じく ``CreateCustomObjectPath('StructuralMember', path, profile)`` で構造材を
配置するが、**傾き(勾配)の与え方が異なる**。あちらはストーリのあるモデルに
配置するため傾きを始端/終端の高さバインド(``SetObjectStoryBound``)で与え、パスは
水平にする(パスにも Z を持たせると高さバインドが加算されて傾きが二重になるため)。

こちらは**ストーリを持たない単独の PIO** の中で垂木を描くため高さバインドは
使えない。代わりに**傾きをパス(3D)そのものに持たせる**(始端 (0,0,0) から
終端 (dx, dy, 立ち上がり) の 3D パス)。高さバインドを併用しないので二重加算は
起きない。パスをローカル原点で作ってから ``Move3D`` で始端の実位置へ移動する。
"""
from __future__ import annotations

from typing import Any

import vs

from ..document import RafterCommand

PLUGIN_NAME = 'StructuralMember'


def draw_rafter(command: RafterCommand) -> Any:
    """rafter 命令 1 件を構造材ツールで描画し、配置した構造材ハンドルを返す。

    プラグインが利用できずフォールバック(通常線)で描画した場合は None を返す。

    パスはローカル原点 (0,0,0) から終端方向ベクトル (dx, dy, 立ち上がり) の
    3D パスで作り、``Move3D`` で始端(軒側)の実位置へ移動する。傾き(勾配)は
    このパスの Z 成分で表す(ストーリの無い単独 PIO のため高さバインドは使わない)。
    """
    x1, y1 = command['start']
    x2, y2 = command['end']
    z1 = command['elevation']
    z2 = command['end_elevation']

    # パスをローカル座標で作成(始点=原点、終点=方向ベクトル)。傾きは Z 成分で表す。
    path_h = vs.CreateNurbsCurve(0, 0, 0, False, 1)
    vs.AddVertex3D(path_h, x2 - x1, y2 - y1, z2 - z1)

    w = int(round(command['width']))
    h = int(round(command['height']))
    vs.BeginGroup()
    vs.ClosePoly()
    vs.Poly(0, 0, 0, h, w, h, w, 0)
    vs.EndGroup()
    profile_h = vs.LNewObj()

    obj = vs.CreateCustomObjectPath(PLUGIN_NAME, path_h, profile_h)
    if obj != vs.Handle(0):
        # ローカル原点から始端(軒側)の実位置へ移動
        vs.ResetOrientation3D()
        vs.Move3D(x1, y1, z1)
        vs.SetClass(obj, command['class'])
        vs.SetRField(obj, PLUGIN_NAME, 'MemberID', command['member_id'])
        # 断面寸法は垂木の Width/Height から決める(矩形断面のため Minor も同値)。
        vs.SetRField(obj, PLUGIN_NAME, 'MajorBreadth', str(w))
        vs.SetRField(obj, PLUGIN_NAME, 'MajorDepth', str(h))
        vs.SetRField(obj, PLUGIN_NAME, 'MinorBreadth', str(w))
        vs.SetRField(obj, PLUGIN_NAME, 'MinorDepth', str(h))
        # 軸組ツール(StructuralMember)からプロキシしたパラメータを、同名の
        # レコードフィールドへそのまま転送する(document.MEMBER_FIELD_MAP の対応)。
        vs.SetRField(obj, PLUGIN_NAME, 'ProfileShape', command['profile_shape'])
        vs.SetRField(obj, PLUGIN_NAME, 'ProfileSeries', command['profile_series'])
        vs.SetRField(obj, PLUGIN_NAME, 'MemberType', command['member_type'])
        vs.SetRField(
            obj, PLUGIN_NAME, 'StructuralUse', command['structural_use'])
        vs.SetRField(obj, PLUGIN_NAME, 'AxisAlign', command['axis_align'])
        vs.SetRField(
            obj, PLUGIN_NAME, 'StartCondition', command['start_condition'])
        vs.SetRField(obj, PLUGIN_NAME, 'EndCondition', command['end_condition'])
        vs.SetRField(obj, PLUGIN_NAME, 'MemberMaterial', command['material'])
        vs.ResetObject(obj)
        return obj
    # フォールバック: 通常の直線(水平投影)
    vs.MoveTo(x1, y1)
    vs.LineTo(x2, y2)
    fallback_line = vs.LNewObj()
    vs.SetClass(fallback_line, command['class'])
    return None


def execute_rafters(commands: list[RafterCommand]) -> int:
    """rafter 命令のリストを描画し、配置数を返す。

    垂木は PIO(``run()``)の中で、PIO が置かれたレイヤにそのまま描かれるため、
    横架材インポートのようなレイヤ切り替え(``vs.Layer``)は行わない。
    フォールバック描画(プラグイン不可)も配置数に数える(何らかの図形は描くため)。
    """
    count = 0
    for command in commands:
        draw_rafter(command)
        count += 1
    return count
