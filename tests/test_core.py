"""Tests for core primitives: ids and hashing."""

from __future__ import annotations

from ala.core import ids
from ala.core.hashing import sha256_bytes, sha256_file, sha256_text


def test_slugify_basic():
    assert ids.slugify("Week 3: Constraints & Relationships!") == "week-3-constraints-relationships"


def test_slugify_arabic_falls_back_but_never_empty():
    slug = ids.slugify("المفتاح الأجنبي")  # non-ASCII -> transliterates/drops
    assert slug  # always non-empty
    assert all(c.isascii() for c in slug)


def test_make_and_validate_resource_id():
    rid = ids.make_resource_id("technical", "dmv", "w03", "Constraints and Relationships")
    assert rid == "technical.dmv.w03.constraints-and-relationships"
    assert ids.is_valid_resource_id(rid)


def test_invalid_resource_ids_rejected():
    assert not ids.is_valid_resource_id("only.two")          # <3 segments
    assert not ids.is_valid_resource_id("Bad.UPPER.case.x")  # uppercase
    assert not ids.is_valid_resource_id("a.b.c d")           # space


def test_sha256_is_deterministic_and_matches_bytes(tmp_path):
    known = sha256_text("hello")
    assert known == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    assert sha256_file(f) == sha256_bytes(b"hello") == known
