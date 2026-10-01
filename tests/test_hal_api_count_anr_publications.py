from datetime import date
from urllib.parse import parse_qs, urlparse

import hal_api.api_count_anr_publications as anr_module
from hal_api.api_count_anr_publications import (
    build_period_applied,
    count_anr_publications_hal,
    count_anr_publications_logic,
)


def test_build_period_applied_with_no_bounds():
    assert build_period_applied(None, None) == "aucune restriction (toutes dates confondues)"


def test_build_period_applied_with_both_bounds():
    period = build_period_applied(date(2020, 1, 1), date(2023, 12, 31))
    assert period == "2020-01-01 – 2023-12-31"


def test_build_period_applied_with_only_start():
    period = build_period_applied(date(2020, 1, 1), None)
    assert period == "2020-01-01 – ..."


async def test_count_anr_publications_hal_builds_filters(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 12}})

    result = await count_anr_publications_hal(
        struct_id=194495, start_date=date(2020, 1, 1), end_date=date(2020, 12, 31), open_access=False
    )

    assert result["num_found"] == 12
    params = client.calls[0]["params"]
    assert params["rows"] == 0
    assert params["fq"] == [
        "anrProjectId_i:[* TO *]",
        "structId_i:194495",
        "-openAccess_bool:true",
        "producedDate_tdate:[2020-01-01T00:00:00Z TO 2020-12-31T23:59:59Z]",
    ]


async def test_count_anr_publications_logic_returns_open_access_breakdown(monkeypatch):
    async def fake_count(struct_id, start_date, end_date, open_access=None):
        if open_access:
            return {"num_found": 30, "query_url": "url-oa"}
        return {"num_found": 40, "query_url": "url-total"}

    monkeypatch.setattr(anr_module, "count_anr_publications_hal", fake_count)

    result = await count_anr_publications_logic(struct_id=194495)

    urls = result.pop("verification_urls")
    assert result == {
        "struct_id": 194495,
        "period_applied": "aucune restriction (toutes dates confondues)",
        "total_anr_publications": 40,
        "open_access": 30,
        "not_open_access": 10,
        "open_access_rate": 0.75,
        "query_urls": {"total": "url-total", "open_access": "url-oa"},
    }
    fq_by_key = {key: parse_qs(urlparse(url).query)["fq"] for key, url in urls.items()}
    assert fq_by_key == {
        "total": ["anrProjectId_i:[* TO *]", "structId_i:194495"],
        "open_access": ["anrProjectId_i:[* TO *]", "structId_i:194495", "openAccess_bool:true"],
        "not_open_access": ["anrProjectId_i:[* TO *]", "structId_i:194495", "-openAccess_bool:true"],
    }


async def test_count_anr_publications_logic_rate_is_none_when_no_publication(monkeypatch):
    async def fake_count(struct_id, start_date, end_date, open_access=None):
        return {"num_found": 0, "query_url": "url"}

    monkeypatch.setattr(anr_module, "count_anr_publications_hal", fake_count)

    result = await count_anr_publications_logic(struct_id=194495)

    assert result["open_access_rate"] is None


async def test_count_anr_publications_logic_propagates_error(monkeypatch):
    async def fake_count(struct_id, start_date, end_date, open_access=None):
        return {"error": "boom", "query_url": None}

    monkeypatch.setattr(anr_module, "count_anr_publications_hal", fake_count)

    result = await count_anr_publications_logic(struct_id=194495)

    assert result == {"error": "boom", "query_url": None}


async def test_count_anr_publications_logic_rejects_inverted_period():
    result = await count_anr_publications_logic(
        struct_id=194495,
        start_date=date(2023, 1, 1),
        end_date=date(2020, 1, 1),
    )

    assert "error" in result
