"""Tests for the ResourceMetadata schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from ala.core.enums import DocType, Language
from ala.metadata.schema import ResourceMetadata


def test_minimal_construction_and_defaults(make_meta):
    m = make_meta()
    assert m.schema_version == "2.0.0"
    assert m.lifecycle.version == 1
    assert m.status.processing_status == "pending"        # use_enum_values -> str
    assert m.retrieval.chunk_count == 0
    assert m.language == "en"


def test_round_trip_json(make_meta):
    m = make_meta(doc_type=DocType.LESSON_PAGE, language=Language.AR, is_translation=True)
    restored = ResourceMetadata.from_dict(m.to_dict())
    assert restored == m
    assert restored.language == "ar"


def test_enums_serialize_as_strings(make_meta):
    d = make_meta(doc_type=DocType.LECTURE_SLIDES).to_dict()
    assert d["doc_type"] == "lecture_slides"
    assert d["status"]["processing_status"] == "pending"


def test_invalid_resource_id_rejected():
    with pytest.raises(PydanticValidationError):
        ResourceMetadata(
            resource_id="NOT VALID",
            title="x",
            track="technical",
            course="dmv",
            module="w03",
            file={"file_name": "a", "file_path": "a"},
        )


def test_catalog_row_has_promoted_columns(make_meta):
    row = make_meta().to_catalog_row()
    for col in ("resource_id", "sha256", "processing_status", "doc_type", "language", "version"):
        assert col in row


def test_extra_fields_forbidden(make_meta):
    with pytest.raises(PydanticValidationError):
        ResourceMetadata(
            resource_id="technical.dmv.w03.x",
            title="x",
            track="technical",
            course="dmv",
            module="w03",
            file={"file_name": "a", "file_path": "a"},
            bogus_field=123,
        )
