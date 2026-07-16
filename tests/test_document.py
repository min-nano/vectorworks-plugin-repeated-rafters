"""命令セットのスキーマ検証 (document.validate_document) のテスト。vs 非依存。"""
from __future__ import annotations

import copy

import pytest

from vectorworks_plugin_repeated_rafters.document import (
    DOCUMENT_VERSION,
    RafterCommand,
    DocumentValidationError,
    validate_document,
)


def make_rafter(
    origin: tuple[float, float] = (0.0, 0.0),
    angle: float = 90.0,
    span: float = 3000.0,
    overhang: float = 455.0,
    pitch: float = 21.8,
    width: float = 45.0,
    height: float = 60.0,
    rafter_class: str = '04構造-02木造-05小屋組-05垂木',
    label: str = '45×60@455',
) -> RafterCommand:
    return {
        'class': rafter_class,
        'label': label,
        'origin': list(origin),
        'angle': angle,
        'span': span,
        'overhang': overhang,
        'pitch': pitch,
        'width': width,
        'height': height,
        'config': 'SWB',
        'bearing_inset': '52.5',
        'eave_style': 'vertical',
        'fascia_height': '60',
        'vertical_reference': 'top',
        'material': 'Wood',
    }


def make_document(rafters: list[RafterCommand] | None = None) -> dict:
    return {
        'version': DOCUMENT_VERSION,
        'rafters': [make_rafter()] if rafters is None else rafters,
    }


class TestValidateDocument:
    def test_valid_document_passes(self) -> None:
        doc = make_document()
        assert validate_document(doc) is doc

    def test_empty_rafters_is_valid(self) -> None:
        doc = make_document(rafters=[])
        assert validate_document(doc) is doc

    def test_rejects_non_dict(self) -> None:
        with pytest.raises(DocumentValidationError):
            validate_document([])

    def test_rejects_wrong_version(self) -> None:
        doc = make_document()
        doc['version'] = DOCUMENT_VERSION + 1
        with pytest.raises(DocumentValidationError):
            validate_document(doc)

    def test_rejects_missing_rafters(self) -> None:
        with pytest.raises(DocumentValidationError):
            validate_document({'version': DOCUMENT_VERSION})

    def test_rejects_rafters_not_list(self) -> None:
        with pytest.raises(DocumentValidationError):
            validate_document({'version': DOCUMENT_VERSION, 'rafters': {}})

    def test_rejects_empty_class(self) -> None:
        doc = make_document(rafters=[make_rafter(rafter_class='')])
        with pytest.raises(DocumentValidationError):
            validate_document(doc)

    def test_rejects_non_point_origin(self) -> None:
        rafter = make_rafter()
        rafter['origin'] = [0.0]
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_rejects_non_number_width(self) -> None:
        rafter = make_rafter()
        rafter['width'] = 'wide'  # type: ignore[typeddict-item]
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_rejects_nan_span(self) -> None:
        rafter = make_rafter()
        rafter['span'] = float('nan')
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_rejects_negative_overhang(self) -> None:
        rafter = make_rafter(overhang=-1.0)
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_zero_overhang_is_valid(self) -> None:
        doc = make_document(rafters=[make_rafter(overhang=0.0)])
        assert validate_document(doc) is doc

    def test_rejects_non_string_proxied_field(self) -> None:
        rafter = make_rafter()
        rafter['config'] = 1  # type: ignore[typeddict-item]
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_proxied_material_may_be_empty(self) -> None:
        # material は空文字(材質無指定)でも検証を通る。
        doc = make_document(rafters=[make_rafter()])
        doc['rafters'][0]['material'] = ''
        assert validate_document(doc) is doc

    def test_label_may_be_empty(self) -> None:
        # label は文字列であれば空でも良い(検証は非空を要求しない)
        doc = make_document(rafters=[make_rafter(label='')])
        assert validate_document(doc) is doc

    def test_does_not_mutate_input(self) -> None:
        doc = make_document()
        before = copy.deepcopy(doc)
        validate_document(doc)
        assert doc == before
