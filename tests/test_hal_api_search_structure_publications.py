from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

import hal_api.api_search_structure_publications as module
from hal_api.api_search_structure_publications import build_structure_fq, search_structure_publications

SEARCH_DATA = {
    "response": {
        "numFound": 268,
        "docs": [
            {
                "halId_s": "hal-1",
                "uri_s": "https://hal.science/hal-1",
                "title_s": ["Hommages dans les universités"],
                "authFullName_s": ["A", "B"],
                "producedDate_s": "2026-09-10",
                "producedDateY_i": 2026,
                "docType_s": "ART",
                "doiId_s": "10.1234/x",
                "journalTitle_s": "Revue X",
                # structure demandée + hiérarchie (tutelles) non demandée
                "structId_i": [1005874, 154357, 307249],
            },
            {
                "halId_s": "hal-2",
                "title_s": "Wikimania",
                "docType_s": "COMM",
                "conferenceTitle_s": "Wikimania 2026",
                "structId_i": [484158],
            },
        ],
    },
    "facet_counts": {"facet_queries": {"structId_i:1005874": 52, "structId_i:154357": 81, "structId_i:484158": 72}},
}

REF = {
    "structures": {
        1005874: {"id": "1005874", "name": "URFIST", "acronym": "URFIST de Lyon", "parent_names": [], "validation_status": "VALID"},
        154357: {"id": "154357", "name": "URFIST", "acronym": "URFIST Paris", "parent_names": ["École nationale des chartes"], "validation_status": "VALID"},
    },
    "query_url": "ref-url",
}


@pytest.fixture
def fake_hal(monkeypatch):
    calls = {}

    def install(search=None, ref=None):
        async def fake_hal_get(url, params):
            calls["params"] = params
            return search if search is not None else {"data": SEARCH_DATA, "query_url": "search-url"}

        async def fake_ref(struct_ids):
            calls["ref_ids"] = struct_ids
            return ref if ref is not None else REF

        monkeypatch.setattr(module, "hal_get", fake_hal_get)
        monkeypatch.setattr(module, "hal_api_get_structures_by_ids", fake_ref)
        return calls

    return install


def test_build_structure_fq_combines_structures_period_and_types():
    fq = build_structure_fq([1, 2], date(2024, 1, 1), None, ["ART"])

    assert fq == [
        "structId_i:(1 OR 2)",
        "producedDate_tdate:[2024-01-01T00:00:00Z TO *]",
        "docType_s:(ART)",
    ]


async def test_returns_publications_with_links_and_matched_structures(fake_hal):
    calls = fake_hal()

    result = await search_structure_publications([1005874, 154357, 484158, 1005874], rows=2)

    assert result["num_found"] == 268
    assert result["has_more"] is True
    first_pub, second_pub = result["publications"]
    assert first_pub["url"] == "https://hal.science/hal-1"
    assert first_pub["doi_url"] == "https://doi.org/10.1234/x"
    assert first_pub["venue"] == "Revue X"
    # seules les structures demandées, pas la tutelle 307249
    assert first_pub["struct_ids"] == [154357, 1005874]
    assert second_pub["doi_url"] is None
    assert second_pub["venue"] == "Wikimania 2026"

    params = calls["params"]
    assert params["sort"] == "producedDate_tdate desc"
    # doublon 1005874 retiré
    assert params["fq"] == ["structId_i:(1005874 OR 154357 OR 484158)"]
    assert calls["ref_ids"] == [1005874, 154357, 484158]


async def test_structures_are_named_counted_and_have_verification_links(fake_hal):
    fake_hal()

    result = await search_structure_publications([1005874, 484158], start_date=date(2025, 1, 1))

    lyon, occitanie = result["structures"]
    assert lyon["acronym"] == "URFIST de Lyon"
    assert lyon["num_publications"] == 52
    # absente du référentiel simulé : on garde l'id et le comptage
    assert occitanie["acronym"] is None
    assert occitanie["num_publications"] == 72

    lyon_fq = parse_qs(urlparse(lyon["verification_url"]).query)["fq"]
    assert lyon_fq == ["structId_i:1005874", "producedDate_tdate:[2025-01-01T00:00:00Z TO *]"]
    all_params = parse_qs(urlparse(result["verification_url"]).query)
    assert all_params["sort"] == ["producedDate_tdate desc"]


async def test_referential_failure_does_not_block_publications(fake_hal):
    fake_hal(ref={"error": "ref down", "query_url": None})

    result = await search_structure_publications([1005874])

    assert len(result["publications"]) == 2
    assert result["structures"][0]["name"] is None
    assert "ref down" in result["structures_warning"]


async def test_search_failure_is_propagated(fake_hal):
    fake_hal(search={"error": "boom", "query_url": "u"})

    result = await search_structure_publications([1005874])

    assert result == {"error": "boom", "query_url": "u"}


async def test_invalid_doc_type_is_rejected(fake_hal):
    calls = fake_hal()

    result = await search_structure_publications([1005874], doc_types=["ART OR *:*"])

    assert "invalide" in result["error"]
    assert "params" not in calls