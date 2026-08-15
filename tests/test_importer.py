"""Tests for the CorpusImporter classification + disposition."""

from __future__ import annotations

from ala.ingestion.importer import CorpusImporter, Disposition


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    return path


def test_corpus_classification_and_disposition(settings, tmp_path):
    src = tmp_path / "src"
    _touch(src / "Applied Deep Learning-20260722T062121Z-1-001" / "Applied Deep Learning"
           / "Week5 - CNNs" / "Practical-DL-Lec5.pdf")
    _touch(src / "English" / "Session 3 - Introduce.pdf")
    _touch(src / "EXCEL-AI tools-20260722T062118Z-1-001" / "EXCEL-AI tools" / "Week 2"
           / "session 1" / "Work File.xlsx")
    _touch(src / "Introduction to AI and Machine Learning" / "client_secret_x.json")
    _touch(src / "Data_Minig" / "week 5 revision" / "EDA.ipynb.txt")
    _touch(src / "Data_Minig" / "week 5 revision" / "big.crdownload")

    plan = CorpusImporter(settings).plan(src)
    by = {i.source.name: i for i in plan.items}

    dl = by["Practical-DL-Lec5.pdf"]
    assert dl.disposition is Disposition.COPY
    assert (dl.track, dl.course, dl.module) == ("technical", "applied-dl", "w05")
    assert "raw/technical/applied-dl/w05/" in dl.dest_rel

    assert (by["Session 3 - Introduce.pdf"].track, by["Session 3 - Introduce.pdf"].course) == \
        ("nontechnical", "eng")

    xl = by["Work File.xlsx"]
    assert xl.disposition is Disposition.COPY_DATASET
    assert (xl.course, xl.module) == ("excel-ai", "w02-s1")

    assert by["client_secret_x.json"].disposition is Disposition.QUARANTINE
    assert by["EDA.ipynb.txt"].disposition is Disposition.SKIP
    assert by["big.crdownload"].disposition is Disposition.SKIP


def test_unique_dest_avoids_collisions(settings, tmp_path):
    src = tmp_path / "src"
    _touch(src / "Data_Minig" / "week 1" / "notes.pdf")
    _touch(src / "Data_Minig" / "week 1" / "sub" / "notes.pdf")   # same stem, same week
    plan = CorpusImporter(settings).plan(src)
    dests = [i.dest_rel for i in plan.items if i.dest_rel]
    assert len(dests) == len(set(dests))       # no duplicate destinations
