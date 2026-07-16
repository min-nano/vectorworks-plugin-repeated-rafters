"""JSON 命令セット(ドキュメント)のスキーマ定義と検証。

命令セットはジオメトリ計算フェーズ(``rafters`` パッケージ)が生成し、
描画フェーズ(``vw`` パッケージ)が消費する JSON 直列化可能な dict。
このモジュールは vs にも VectorWorks にも依存しない。

姉妹プロジェクト vectorworks_plugin_import_ifc_homeskz と同じ
「2 フェーズ分離 + JSON 命令セット」の設計を踏襲している。あちらは IFC を
解析して多種のオブジェクトを描くのに対し、こちらは 1 種類のオブジェクト
(垂木=軸組ツール ``FramingMember``)だけを描くため、命令セットは ``rafters``
の 1 リストだけを持つ(将来、母屋・鼻母屋などを追加する場合はここへ命令種別を足す)。

垂木は VectorWorks の**軸組ツール(``FramingMember``, ``type='rafter'``)**で描く。
``FramingMember`` の rafter は**点 + 平面回転**で配置する PIO で、地廻り基準線(支持点の
線)を原点(データム)とし、そこから棟側へ ``span`` の水平長で本体を、軒側へ ``overhang``
の水平長で軒の出を描く。傾きは ``pitch``(勾配角)で与える。

スキーマ (version 3):

    {
        "version": 3,
        "rafters": [
            {
                # 垂木 1 本を軸組ツール(FramingMember, type='rafter')で描く命令。
                # class は PIO オブジェクト自身のクラス(垂木もこのクラスに置く)。
                "class": "04構造-02木造-05小屋組-05垂木",  # 割り当てるクラス名
                "label": "45×60@455",       # 表示ラベル (FramingMember の labelText)
                # origin は地廻り基準線上の配置点(平面, PIO ローカル座標 mm)。
                # 高さ 0 のデータム。angle は棟方向(垂木が伸びる向き)の平面回転(度)。
                "origin": [x, y],
                "angle": 30.0,
                # span は地廻り→棟の水平長(本体), overhang は地廻り→軒先の水平長
                # (軒の出, >=0)。いずれも屋根水平投影面(パス)でクリップして得る。
                "span": 4000.0,
                "overhang": 455.0,
                "pitch": 21.8,               # 勾配角(度) = atan(寸勾配/10)
                "width": 45.0,               # 垂木幅 (mm)
                "height": 60.0,              # 垂木成 (mm)
                # 以下は「軸組ツール(FramingMember)で設定するパラメータ」を PIO
                # パラメータとして公開し、描画フェーズへプロキシ(そのまま転送)する
                # 値。描画フェーズは各値を MEMBER_FIELD_MAP に従い FramingMember の
                # レコードフィールドへ SetRField する。垂木の要点のみを対象とする。
                "config": "SWB",             # 部材構成 (config)
                "bearing_inset": "52.5",     # 支持点の食い込み (bearinginset)
                "eave_style": "vertical",    # 軒先(鼻隠し)の形状 (eavestyle)
                "fascia_height": "60",       # 鼻隠し成 (fasciaheight)
                "vertical_reference": "top", # 高さ基準 (verticalReference)
                "material": "Wood",          # 材質 (Material)
                "display_2d": "width"        # 2D 表現 (2DDisplay)
            }
        ]
    }
"""
from __future__ import annotations

import json
from typing import Any, TypedDict

DOCUMENT_VERSION = 3

# 軸組ツール(FramingMember)からプロキシする文字列フィールド。命令セットの
# キー名を FramingMember のレコードフィールド名へ対応付ける。描画フェーズは
# この対応に従い、各値をそのまま ``SetRField`` へ転送する(垂木の要点のみ)。
MEMBER_FIELD_MAP: dict[str, str] = {
    'config': 'config',
    'bearing_inset': 'bearinginset',
    'eave_style': 'eavestyle',
    'fascia_height': 'fasciaheight',
    'vertical_reference': 'verticalReference',
    'material': 'Material',
    # 2D 表現(実線/中心線/幅/中心線と幅/面なし = solid/center/width/
    # widthcenter/none)を切り替える FramingMember のフィールド。
    'display_2d': '2DDisplay',
}


# 'class' キーが Python の予約語のため functional 構文で定義する
RafterCommand = TypedDict('RafterCommand', {
    'class': str,
    'label': str,
    'origin': list[float],
    'angle': float,
    'span': float,
    'overhang': float,
    'pitch': float,
    'width': float,
    'height': float,
    # 軸組ツール(FramingMember)からプロキシする値(MEMBER_FIELD_MAP のキー)。
    'config': str,
    'bearing_inset': str,
    'eave_style': str,
    'fascia_height': str,
    'vertical_reference': str,
    'material': str,
    'display_2d': str,
})
"""垂木 1 本を軸組ツール(FramingMember, type='rafter')で描画する命令。

origin は地廻り基準線上の配置点(平面, 高さ 0 のデータム)。angle は棟方向の平面回転
(度)。span は地廻り→棟の水平長(本体)、overhang は地廻り→軒先の水平長(軒の出, >=0)。
pitch は勾配角(度)。width/height は断面。class は割り当てるクラス名(PIO オブジェクト
自身のクラス)、label は "{幅}×{成}@{間隔}" 形式の表示ラベル。

config 以降は「軸組ツール(FramingMember)で設定するパラメータ」を PIO パラメータ
として公開し、描画フェーズへプロキシ(そのまま転送)する値。描画フェーズは
``MEMBER_FIELD_MAP`` に従い各値を FramingMember の同名レコードフィールドへ設定する。
垂木の要点のみを対象とし、断面形状の各種オプション等は VectorWorks の既定に委ねる。
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
    _require(isinstance(command.get('label'), str),
             f'{where}.label は文字列である必要があります')
    _require(_is_point(command.get('origin')),
             f'{where}.origin は [x, y] の数値ペアである必要があります')
    for key in ('angle', 'span', 'overhang', 'pitch', 'width', 'height'):
        _require(_is_number(command.get(key)),
                 f'{where}.{key} は数値である必要があります')
    # overhang(軒の出)は負にならない。
    _require(command.get('overhang', 0) >= 0,
             f'{where}.overhang は 0 以上である必要があります')
    # 軸組ツールからプロキシする値はいずれも文字列(空文字も可)。
    for key in MEMBER_FIELD_MAP:
        _require(isinstance(command.get(key), str),
                 f'{where}.{key} は文字列である必要があります')


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
