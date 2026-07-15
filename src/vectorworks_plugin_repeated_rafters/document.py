"""JSON 命令セット(ドキュメント)のスキーマ定義と検証。

命令セットはジオメトリ計算フェーズ(``rafters`` パッケージ)が生成し、
描画フェーズ(``vw`` パッケージ)が消費する JSON 直列化可能な dict。
このモジュールは vs にも VectorWorks にも依存しない。

姉妹プロジェクト vectorworks_plugin_import_ifc_homeskz と同じ
「2 フェーズ分離 + JSON 命令セット」の設計を踏襲している。あちらは IFC を
解析して多種のオブジェクトを描くのに対し、こちらは 1 種類のオブジェクト
(垂木=StructuralMember)だけを描くため、命令セットは ``rafters`` の 1 リスト
だけを持つ(将来、母屋・鼻母屋などを追加する場合はここへ命令種別を足す)。

スキーマ (version 1):

    {
        "version": 1,
        "rafters": [
            {
                # 垂木 1 本を VectorWorks の構造材ツール(軸組ツール、
                # StructuralMember)で描く命令。
                "class": "04構造-02木造-05小屋組-05垂木",  # 割り当てるクラス名
                "member_id": "45×60 - 垂木",   # 構造材 ID (StructuralMember の MemberID)
                # start/end は垂木の水平投影(平面)線。start は地廻り基準線
                # (軒側)上の点、end は屋根水平投影面の反対側の縁(棟側)の点。
                # いずれも PIO のローカル座標(mm)。
                "start": [x1, y1],
                "end": [x2, y2],
                "width": 45.0,            # 垂木幅 (mm, 基準線方向の断面寸法)
                "height": 60.0,           # 垂木成 (mm, 断面のもう一方の寸法)
                # 垂木は勾配なりに傾く。elevation=始端(軒側)の Z、
                # end_elevation=終端(棟側)の Z。差(end_elevation - elevation)が
                # 立ち上がり = 水平投影長 × 勾配/10。描画フェーズはこの傾きを
                # パス(3D)そのものに持たせて描く(ストーリの無い単独 PIO のため
                # 高さバインドは使わない)。
                "elevation": 0.0,
                "end_elevation": 300.0
            }
        ]
    }
"""
from __future__ import annotations

import json
from typing import Any, TypedDict

DOCUMENT_VERSION = 1


# 'class' キーが Python の予約語のため functional 構文で定義する
RafterCommand = TypedDict('RafterCommand', {
    'class': str,
    'member_id': str,
    'start': list[float],
    'end': list[float],
    'width': float,
    'height': float,
    'elevation': float,
    'end_elevation': float,
})
"""垂木 1 本を構造材ツール(StructuralMember)で描画する命令。

start/end は垂木の水平投影線(始端=地廻り基準線=軒側、終端=屋根投影面の
反対側の縁=棟側)。elevation/end_elevation は始端/終端の Z 高さで、差が
勾配なりの立ち上がり(= 水平投影長 × 勾配/10)。class は割り当てる構造クラス名、
member_id は "{幅}×{成} - 垂木" 形式の構造材 ID。
"""


class Document(TypedDict):
    """ジオメトリ計算フェーズと描画フェーズを接続する命令セット全体。"""

    version: int
    rafters: list[RafterCommand]


class DocumentValidationError(ValueError):
    """命令セットがスキーマに適合しない場合に送出される。"""


def _require(condition: object, message: str) -> None:
    if not condition:
        raise DocumentValidationError(message)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_point(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(_is_number(c) for c in value)
    )


def _validate_rafter(index: int, command: Any) -> None:
    where = f'rafters[{index}]'
    _require(isinstance(command, dict), f'{where} は dict である必要があります')
    _require(isinstance(command.get('class'), str) and command['class'],
             f'{where}.class は非空文字列である必要があります')
    _require(isinstance(command.get('member_id'), str),
             f'{where}.member_id は文字列である必要があります')
    _require(_is_point(command.get('start')),
             f'{where}.start は [x, y] の数値ペアである必要があります')
    _require(_is_point(command.get('end')),
             f'{where}.end は [x, y] の数値ペアである必要があります')
    for key in ('width', 'height', 'elevation', 'end_elevation'):
        _require(_is_number(command.get(key)),
                 f'{where}.{key} は数値である必要があります')


def validate_document(document: Any) -> Document:
    """命令セットを検証し、不正な場合は DocumentValidationError を送出する。"""
    _require(isinstance(document, dict), '命令セットは dict である必要があります')
    _require(document.get('version') == DOCUMENT_VERSION,
             f'未対応の命令セットバージョンです: {document.get("version")!r}')
    _require(isinstance(document.get('rafters'), list),
             '"rafters" はリストである必要があります')
    for i, command in enumerate(document['rafters']):
        _validate_rafter(i, command)
    try:
        # スキーマ検証だけでは未知キー配下の非直列化値を検出できないため、
        # JSON 直列化可能性も明示的に検証する (NaN/Infinity も拒否)
        json.dumps(document, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise DocumentValidationError(
            f'命令セットは JSON 直列化可能である必要があります: {e}'
        ) from e
    return document
