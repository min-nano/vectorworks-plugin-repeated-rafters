"""フェーズ1: ジオメトリ計算。

屋根の水平投影面(PIO のパス)と各パラメータから、描画フェーズ(``vw``
パッケージ)への入力となる JSON 直列化可能な命令セット(ドキュメント)を
組み立てる。このパッケージは vs(VectorWorks API)に一切依存しない。
"""
from __future__ import annotations

from ..document import DOCUMENT_VERSION, Document
from .geometry import build_rafter_commands, make_label

__all__ = ['build_document', 'build_rafter_commands', 'make_label']


def build_document(
    path: list[list[float]],
    *,
    base_line: list[list[float]] | None,
    slope: float,
    width: float,
    height: float,
    spacing: float,
    rafter_class: str,
    config: str,
    bearing_inset: str,
    eave_style: str,
    fascia_height: str,
    vertical_reference: str,
    material: str,
) -> Document:
    """屋根水平投影面と各パラメータから JSON 命令セットを組み立てて返す。

    Args:
        path: 屋根水平投影面の外形頂点列 [[x, y], ...](PIO のパス。閉ポリゴン。
            軒先まで含む面)。
        base_line: 地廻り基準線の 2 端点 [[x1, y1], [x2, y2]](コントロール
            ポイント)。``None`` や退化した線の場合はパスの最初の辺を基準辺に使う。
        slope: 寸勾配(10 の水平に対する立ち上がり)。
        width: 垂木幅 (mm)。
        height: 垂木成 (mm)。
        spacing: 垂木の間隔 (mm)。
        rafter_class: 各垂木に割り当てる作図クラス名。
        config: 軸組ツール(FramingMember)からプロキシする部材構成 (``config``)。
            以下 5 つと共に描画フェーズへそのまま転送する(垂木の要点のみ)。
        bearing_inset: 支持点の食い込み (``bearinginset``)。
        eave_style: 軒先(鼻隠し)の形状 (``eavestyle``)。
        fascia_height: 鼻隠し成 (``fasciaheight``)。
        vertical_reference: 高さ基準 (``verticalReference``)。
        material: 材質 (``Material``)。
    """
    return {
        'version': DOCUMENT_VERSION,
        'rafters': build_rafter_commands(
            path,
            base_line=base_line,
            slope=slope,
            width=width,
            height=height,
            spacing=spacing,
            rafter_class=rafter_class,
            config=config,
            bearing_inset=bearing_inset,
            eave_style=eave_style,
            fascia_height=fascia_height,
            vertical_reference=vertical_reference,
            material=material,
        ),
    }
