"""Unit tests for normalization, language detection, and academic parsing."""

from __future__ import annotations

from ala.fabric.content import BlockType
from ala.fabric.learning_resource import LearningResource
from ala.ingestion.config import NormalizationConfig
from ala.ingestion.text import normalize
from ala.ingestion.text.academic import AcademicStructureDetector
from ala.ingestion.text.language import ScriptLanguageDetector


def test_normalize_smart_chars_and_whitespace():
    cfg = NormalizationConfig()
    dirty = "“Smart”  quotes—dash…\n\n\n\nand   spaces"
    out = normalize.normalize_block_text(dirty, block_type="paragraph", config=cfg)
    assert '"Smart"' in out
    assert "-dash..." in out
    assert "   " not in out
    assert "\n\n\n" not in out


def test_join_broken_lines_reflows_prose_not_sentences():
    assert normalize.join_broken_lines("foreign\nkey") == "foreign key"
    assert normalize.join_broken_lines("End.\nNext") == "End.\nNext"


def test_code_blocks_are_not_reflowed():
    cfg = NormalizationConfig()
    out = normalize.normalize_block_text("def f():\n    return  1", block_type="code", config=cfg)
    assert "\n" in out  # structure preserved for code


def test_find_repeated_header_footer_lines():
    pages = [["HEADER", "a"], ["HEADER", "b"], ["HEADER", "c"]]
    assert "HEADER" in normalize.find_repeated_lines(pages, 0.5)


def test_language_detector_confidence():
    d = ScriptLanguageDetector()
    en = d.detect("This is clearly English text about databases and keys.")
    assert en.language == "en" and en.confidence > 0.9
    ar = d.detect("هذا نص عربي واضح")
    assert ar.language == "ar"
    assert d.detect("123 456 789").confidence == 0.0


def test_academic_detector(make_meta):
    lr = LearningResource.from_metadata(make_meta(title="Week 3: SQL"))
    lr.add_block("Constraints", block_type=BlockType.HEADING)
    lr.add_block("Example: a primary key uniquely identifies a row.", block_type=BlockType.PARAGRAPH)
    lr.add_block("Exercise: write the DDL.", block_type=BlockType.PARAGRAPH)
    s = AcademicStructureDetector().detect(lr)
    assert s.week == 3
    assert "Constraints" in s.topics
    assert s.examples and s.exercises
