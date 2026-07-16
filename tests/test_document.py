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
    start: tuple[float, float] = (0.0, 0.0),
    end: tuple[float, float] = (0.0, 3000.0),
    width: float = 45.0,
    height: float = 60.0,
    elevation: float = 0.0,
    end_elevation: float = 1200.0,
    rafter_class: str = '04構造-02木造-05小屋組-05垂木',
    member_id: str = '45×60 - 垂木',
) -> RafterCommand:
    return {
        'class': rafter_class,
        'member_id': member_id,
        'start': list(start),
        'end': list(end),
        'width': width,
        'height': height,
        'elevation': elevation,
        'end_elevation': end_elevation,
        'profile_shape': 'Rectangle',
        'profile_series': 'AISC (Inch)',
        'member_type': '2',
        'structural_use': '1',
        'axis_align': '1',
        'start_condition': '3',
        'end_condition': '3',
        'material': '',
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

    def test_rejects_non_point_start(self) -> None:
        rafter = make_rafter()
        rafter['start'] = [0.0]
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_rejects_non_number_width(self) -> None:
        rafter = make_rafter()
        rafter['width'] = 'wide'  # type: ignore[typeddict-item]
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_rejects_nan_elevation(self) -> None:
        rafter = make_rafter()
        rafter['end_elevation'] = float('nan')
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_rejects_non_string_proxied_field(self) -> None:
        rafter = make_rafter()
        rafter['structural_use'] = 1  # type: ignore[typeddict-item]
        with pytest.raises(DocumentValidationError):
            validate_document(make_document(rafters=[rafter]))

    def test_proxied_material_may_be_empty(self) -> None:
        # material は空文字(材質無指定)でも検証を通る。
        doc = make_document(rafters=[make_rafter()])
        assert validate_document(doc) is doc

    def test_member_id_may_be_empty(self) -> None:
        # member_id は文字列であれば空でも良い(検証は非空を要求しない)
        doc = make_document(rafters=[make_rafter(member_id='')])
        assert validate_document(doc) is doc

    def test_does_not_mutate_input(self) -> None:
        doc = make_document()
        before = copy.deepcopy(doc)
        validate_document(doc)
        assert doc == before
