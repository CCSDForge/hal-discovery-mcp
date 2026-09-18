from datetime import date

import pytest

import hal_api.api_count_anr_publications as anr_module
from hal_api.api_count_anr_publications import (
    build_period_applied,
    count_anr_publications_logic,
    search_publication_anr_open_access,
)


def test_build_period_applied_with_no_bounds():
    assert build_period_applied(None, None) == "aucune restriction (toutes dates confondues)"


def test_build_period_applied_with_both_bounds():
    period = build_period_applied(date(2020, 1, 1), date(2023, 12, 31))
    assert period == "2020-01-01 – 2023-12-31"


def test_build_period_applied_with_only_start():
    period = build_period_applied(date(2020, 1, 1), None)
    assert period == "2020-01-01 – ..."


async def test_search_publication_anr_open_access_parses_title_list_and_string(fake_aiohttp):
    fake_aiohttp(
        json_data={
            "response": {
                "numFound": 2,
                "docs": [
                    {"title_s": ["Titre en liste"], "docType_s": "ART"},
                    {"title_s": "Titre en chaine", "docType_s": "COMM"},
                ],
            }
        }
    )

    result = await search_publication_anr_open_access(struct_id=194495, rows=10)

    assert result["num_found"] == 2
    titles = [p["title"] for p in result["publications"]]
    assert titles == ["Titre en liste", "Titre en chaine"]


async def test_search_publication_anr_open_access_applies_open_access_filter(fake_aiohttp):
    session = fake_aiohttp(json_data={"response": {"numFound": 0, "docs": []}})

    await search_publication_anr_open_access(open_access=True, rows=10)

    fq_values = session.calls[0]["params"]
    fq_only = [v for k, v in fq_values if k == "fq"]
    assert "openAccess_bool:true" in fq_only


async def test_count_anr_publications_logic_returns_stats_on_success(monkeypatch):
    async def fake_search(**kwargs):
        return {"num_found": 42, "query_url": "http://example.test/?q=*"}

    monkeypatch.setattr(anr_module, "search_publication_anr_open_access", fake_search)

    result = await count_anr_publications_logic(struct_id=194495, open_access=True)

    assert result == {
        "total_matching_hal": 42,
        "open_access_filter": True,
        "struct_id": 194495,
        "period_applied": "aucune restriction (toutes dates confondues)",
        "query_url": "http://example.test/?q=*",
    }


async def test_count_anr_publications_logic_propagates_error(monkeypatch):
    async def fake_search(**kwargs):
        return {"error": "boom", "query_url": None}

    monkeypatch.setattr(anr_module, "search_publication_anr_open_access", fake_search)

    result = await count_anr_publications_logic(struct_id=194495)

    assert result == {"error": "boom", "query_url": None}


async def test_count_anr_publications_logic_rejects_inverted_period():
    with pytest.raises(ValueError):
        await count_anr_publications_logic(
            struct_id=194495,
            start_date=date(2023, 1, 1),
            end_date=date(2020, 1, 1),
        )
