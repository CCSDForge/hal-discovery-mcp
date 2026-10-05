from datetime import date

import httpx
import pytest

from urllib.parse import parse_qs, urlparse

from hal_api.client import (
    SEARCH_URL,
    date_range,
    doc_types_fq,
    documents_url,
    doi_url,
    escape_phrase,
    escape_term,
    first,
    hal_get,
)


def test_documents_url_lists_readable_documents_for_filters():
    url = documents_url(["structId_i:1", "producedDateY_i:2020"])

    assert url.startswith(SEARCH_URL)
    params = parse_qs(urlparse(url).query)
    assert params["q"] == ["*:*"]
    assert params["fq"] == ["structId_i:1", "producedDateY_i:2020"]
    assert params["sort"] == ["producedDate_tdate desc"]
    assert params["wt"] == ["json"]


def test_escape_phrase_escapes_quotes_and_backslashes():
    assert escape_phrase('Jean "JD" Dupont') == 'Jean \\"JD\\" Dupont'
    assert escape_phrase("a\\b") == "a\\\\b"


def test_escape_term_escapes_solr_special_chars_but_not_letters():
    assert escape_term("yutong-fei") == "yutong\\-fei"
    assert escape_term("a b:c*") == "a\\ b\\:c\\*"
    assert escape_term("abc123") == "abc123"


def test_doc_types_fq_builds_filter_and_rejects_injection():
    assert doc_types_fq([]) is None
    assert doc_types_fq(["ART", "THESE"]) == "docType_s:(ART OR THESE)"
    with pytest.raises(ValueError):
        doc_types_fq(["ART) OR (*:*"])


def test_documents_url_without_filters():
    params = parse_qs(urlparse(documents_url(q='authIdHal_s:"x"')).query)

    assert params["q"] == ['authIdHal_s:"x"']
    assert "fq" not in params


def test_date_range_without_bounds_returns_none():
    assert date_range(None, None, "producedDate_tdate") is None


def test_date_range_with_open_upper_bound():
    fq = date_range(date(2020, 1, 1), None, "producedDate_tdate")
    assert fq == "producedDate_tdate:[2020-01-01T00:00:00Z TO *]"


def test_date_range_with_both_bounds_is_inclusive():
    fq = date_range(date(2020, 1, 1), date(2022, 12, 31), "producedDate_tdate")
    assert fq == "producedDate_tdate:[2020-01-01T00:00:00Z TO 2022-12-31T23:59:59Z]"


def test_doi_url_builds_resolver_link():
    assert doi_url("10.1109/ICUAS60882.2024.10556833") == "https://doi.org/10.1109/ICUAS60882.2024.10556833"
    assert doi_url(" 10.1000/a b ") == "https://doi.org/10.1000/a%20b"
    assert doi_url(None) is None
    assert doi_url("") is None


def test_first_handles_list_scalar_and_empty():
    assert first(["a", "b"]) == "a"
    assert first("a") == "a"
    assert first([]) is None
    assert first(None) is None


async def test_hal_get_returns_data_and_forces_json_format(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 1}}, url="http://hal.test/?q=x")

    result = await hal_get("http://hal.test/", {"q": "x"})

    assert result == {"data": {"response": {"numFound": 1}}, "query_url": "http://hal.test/?q=x"}
    assert client.calls[0]["params"] == {"q": "x", "wt": "json"}


async def test_hal_get_returns_error_on_non_200(fake_httpx):
    fake_httpx(status_code=503)

    result = await hal_get("http://hal.test/", {})

    assert "503" in result["error"]
    assert result["query_url"]


async def test_hal_get_detects_html_response(fake_httpx):
    fake_httpx(text_data="<!DOCTYPE html><html></html>", headers={"Content-Type": "text/html"})

    result = await hal_get("http://hal.test/", {})

    assert "HTML" in result["error"]


async def test_hal_get_returns_error_on_invalid_json(fake_httpx):
    fake_httpx(text_data="not json at all")

    result = await hal_get("http://hal.test/", {})

    assert "non-JSON" in result["error"]


async def test_hal_get_returns_error_when_hal_rejects_query_with_200(fake_httpx):
    # Comportement réel de HAL sur une syntaxe Solr invalide (ex: parenthèse non fermée).
    fake_httpx(json_data={"error": {"msg": "Error. See help : /docs"}})

    result = await hal_get("http://hal.test/", {"q": "pratiques (informationnelles"})

    assert "rejeté" in result["error"]
    assert "See help" in result["error"]
    assert result["query_url"]


async def test_hal_get_returns_error_on_network_failure(fake_httpx):
    fake_httpx(raise_on_get=httpx.ConnectError("boom"))

    result = await hal_get("http://hal.test/", {})

    assert "réseau" in result["error"]
    assert result["query_url"] is None


async def test_hal_get_returns_error_on_timeout(fake_httpx):
    fake_httpx(raise_on_get=httpx.ReadTimeout("slow"))

    result = await hal_get("http://hal.test/", {})

    assert "délai" in result["error"]
    assert result["query_url"] is None
