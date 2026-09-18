import pytest

import hal_tools.search_author_publications as tool_module
from hal_tools.search_author_publications import search_author_publications, validate_date


def test_validate_date_accepts_none():
    validate_date(None, "start_date")


def test_validate_date_rejects_bad_format():
    with pytest.raises(ValueError):
        validate_date("15-01-2020", "start_date")


async def test_search_author_publications_counts_abstracts(monkeypatch):
    async def fake_search(author_name, start_date=None, end_date=None, rows=50):
        return [
            {"title": "A", "abstract": "un resume", "year": 2020},
            {"title": "B", "abstract": "Pas de résumé disponible", "year": 2021},
        ]

    monkeypatch.setattr(tool_module, "_search_author_publications", fake_search)

    result = await search_author_publications("Yutong Fei")

    assert result["total"] == 2
    assert result["with_abstract"] == 1
    assert result["without_abstract"] == 1


async def test_search_author_publications_rejects_bad_date_format():
    with pytest.raises(ValueError):
        await search_author_publications("Yutong Fei", start_date="2020/01/01")
