"""rafter 命令の描画。VectorWorks の軸組ツール(FramingMember)で垂木を配置する。

軸組ツール(``FramingMember``, ``type='rafter'``)は**点 + 平面回転**で配置する PIO で、
地廻り基準線上の配置点(``origin``, 高さ 0 のデータム)から棟方向へ ``span`` の水平長で
本体を、軒側へ ``overhang`` の水平長で軒の出を描く。傾き(勾配)は ``pitch``(勾配角)で
与える。姉妹プロジェクトの構造材(``StructuralMember``, 傾斜 3D パス)とは別ツールで、
垂木専用の軒の出・鼻隠し等を持つ。

配置は VectorScript エクスポート(実オブジェクト)の手順に倣う: ``CreateCustomObject``
で生成し、``ResetOrientation3D`` → ``Rotate3D``(Z=棟方向) → ``Move3D``(配置点)で
向き・位置を与えてから、レコードフィールドを設定して ``ResetObject`` する。本体長
(span)・向き・``pitch`` の書式など VW 固有の与え方は、このフェーズで VectorWorks 上で
最終確認する(描画フェーズは他要素と同じく VW 上で検証する方針)。
"""
from __future__ import annotations

import math
from typing import Any

import vs

from ..document import RafterCommand

PLUGIN_NAME = 'FramingMember'


def _fmt(value: float) -> str:
    """寸法・座標を SetRField 用の文字列にする(整数値は末尾の .0 を付けない)。"""
    return f'{value:g}'


def draw_rafter(command: RafterCommand) -> Any:
    """rafter 命令 1 件を軸組ツール(FramingMember)で描画し、配置ハンドルを返す。

    プラグインが利用できずフォールバック(通常線)で描画した場合は None を返す。

    地廻り基準線上の配置点(origin)へ、棟方向(angle)へ回した FramingMember を置く。
    本体長 span は棟側(ローカル +X)への制御点で、軒の出は overhang フィールドで
    与え、傾きは pitch(勾配角)で与える。
    """
    ox, oy = command['origin']
    angle = command['angle']
    span = command['span']
    overhang = command['overhang']
    pitch = command['pitch']
    w = int(round(command['width']))
    h = int(round(command['height']))

    obj = vs.CreateCustomObject(PLUGIN_NAME, 0.0, 0.0, 0.0)
    if obj != vs.Handle(0):
        # 棟方向へ平面回転し、地廻り基準線上の配置点(データム Z=0)へ移動する。
        vs.ResetOrientation3D()
        vs.Rotate3D(0.0, 0.0, angle)
        vs.Move3D(ox, oy, 0.0)
        vs.SetClass(obj, command['class'])
        # 垂木として固定の種別。
        vs.SetRField(obj, PLUGIN_NAME, 'type', 'rafter')
        vs.SetRField(obj, PLUGIN_NAME, 'structuralUse', 'rafter')
        # 断面(mm)。
        vs.SetRField(obj, PLUGIN_NAME, 'width', str(w))
        vs.SetRField(obj, PLUGIN_NAME, 'height', str(h))
        # 傾き(勾配角, 度)・軒の出(水平)・本体長(棟方向=ローカル +X の制御点)。
        vs.SetRField(obj, PLUGIN_NAME, 'pitch', f'{_fmt(pitch)}°')
        vs.SetRField(obj, PLUGIN_NAME, 'PitchAngle', f'{_fmt(pitch)}°')
        vs.SetRField(obj, PLUGIN_NAME, 'overhang', _fmt(overhang))
        vs.SetRField(obj, PLUGIN_NAME, 'ControlPoint01X', _fmt(span))
        vs.SetRField(obj, PLUGIN_NAME, 'ControlPoint01Y', '0')
        vs.SetRField(obj, PLUGIN_NAME, 'labelText', command['label'])
        # 軸組ツールからプロキシした各値を同名フィールドへ転送する
        # (document.MEMBER_FIELD_MAP の対応)。
        vs.SetRField(obj, PLUGIN_NAME, 'config', command['config'])
        vs.SetRField(obj, PLUGIN_NAME, 'bearinginset', command['bearing_inset'])
        vs.SetRField(obj, PLUGIN_NAME, 'eavestyle', command['eave_style'])
        vs.SetRField(obj, PLUGIN_NAME, 'fasciaheight', command['fascia_height'])
        vs.SetRField(
            obj, PLUGIN_NAME, 'verticalReference', command['vertical_reference'])
        vs.SetRField(obj, PLUGIN_NAME, 'Material', command['material'])
        # 2D 表現(実線/中心線/幅/中心線と幅/面なし)。
        vs.SetRField(obj, PLUGIN_NAME, '2DDisplay', command['display_2d'])
        vs.ResetObject(obj)
        return obj
    # フォールバック: 通常の直線(水平投影)。軒先(-overhang)から棟(+span)まで。
    ex = math.cos(math.radians(angle))
    ey = math.sin(math.radians(angle))
    vs.MoveTo(ox - ex * overhang, oy - ey * overhang)
    vs.LineTo(ox + ex * span, oy + ey * span)
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
