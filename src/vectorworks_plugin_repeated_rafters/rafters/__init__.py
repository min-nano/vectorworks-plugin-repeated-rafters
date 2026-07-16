"""フェーズ1: ジオメトリ計算。

屋根の水平投影面(PIO のパス)と各パラメータから、描画フェーズ(``vw``
パッケージ)への入力となる JSON 直列化可能な命令セット(ドキュメント)を
組み立てる。このパッケージは vs(VectorWorks API)に一切依存しない。
"""
from __future__ import annotations

from ..document import DOCUMENT_VERSION, Document
from .geometry import build_rafter_commands, make_member_id

__all__ = ['build_document', 'build_rafter_commands', 'make_member_id']


def build_document(
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
) -> Document:
    """屋根水平投影面と各パラメータから JSON 命令セットを組み立てて返す。

    Args:
        path: 屋根水平投影面の外形頂点列 [[x, y], ...](PIO のパス。閉ポリゴン)。
        base_line: 地廻り基準線の 2 端点 [[x1, y1], [x2, y2]](コントロール
            ポイント)。``None`` や退化した線の場合はパスの最初の辺を基準辺に使う。
        slope: 寸勾配(10 の水平に対する立ち上がり)。
        width: 垂木幅 (mm)。
        height: 垂木成 (mm)。
        spacing: 垂木の間隔 (mm)。
        rafter_class: 各垂木に割り当てる作図クラス名。
        profile_shape: 軸組ツールからプロキシする断面形状 (``ProfileShape``)。
            以下 7 つと共に描画フェーズへそのまま転送する(構造・断面の要点のみ)。
        profile_series: 断面シリーズ (``ProfileSeries``)。
        member_type: 部材タイプ (``MemberType``)。
        structural_use: 構造用途 (``StructuralUse``)。
        axis_align: 軸の位置合わせ (``AxisAlign``)。
        start_condition: 始端条件 (``StartCondition``)。
        end_condition: 終端条件 (``EndCondition``)。
        material: 部材材質 (``MemberMaterial``。空文字は無指定)。
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
            profile_shape=profile_shape,
            profile_series=profile_series,
            member_type=member_type,
            structural_use=structural_use,
            axis_align=axis_align,
            start_condition=start_condition,
            end_condition=end_condition,
            material=material,
        ),
    }
