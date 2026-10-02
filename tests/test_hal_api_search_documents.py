from urllib.parse import parse_qs, urlparse

import pytest

from hal_api.api_search_documents import (
    DEFAULT_FIELDS,
    normalize_fields,
    normalize_sort,
    search_documents,
)


def test_normalize_fields_defaults_when_empty():
    assert normalize_fields(None) == list(DEFAULT_FIELDS)
    assert normalize_fields([]) == list(DEFAULT_FIELDS)
    assert normalize_fields(["  ", ""]) == list(DEFAULT_FIELDS)


def test_normalize_fields_strips_and_deduplicates():
    assert normalize_fields([" halId_s", "title_s", "halId_s"]) == ["halId_s", "title_s"]


@pytest.mark.parametrize("field", ["*", "title_*", "[docid]", "sum(a,b)", "a,b", "a b"])
def test_normalize_fields_rejects_non_plain_names(field):
    with pytest.raises(ValueError):
        normalize_fields([field])


def test_normalize_sort():
    assert normalize_sort(None) is None
    assert normalize_sort("  ") is None
    assert normalize_sort("producedDate_tdate desc") == "producedDate_tdate desc"
    assert normalize_sort("docType_s   asc ,score desc") == "docType_s asc, score desc"


@pytest.mark.parametrize("sort", ["producedDate_tdate", "title_s up", "sum(a,b) desc", "x desc; y asc"])
def test_normalize_sort_rejects_invalid_clauses(sort):
    with pytest.raises(ValueError):
        normalize_sort(sort)


async def test_search_documents_forwards_only_allowed_params(fake_httpx):
    client = fake_httpx(
        json_data={
            "response": {
                "numFound": 42,
                "docs": [{"halId_s": "hal-1", "title_s": ["T"]}, {"halId_s": "hal-2"}],
            }
        }
    )

    result = await search_documents(
        q=" title_t:climat ",
        fq=["docType_s:ART", " ", "producedDateY_i:[2020 TO *]"],
        sort="producedDate_tdate desc",
        rows=2,
        fl=["halId_s", "title_s"],
    )

    params = client.calls[0]["params"]
    assert params == {
        "q": "title_t:climat",
        "fq": ["docType_s:ART", "producedDateY_i:[2020 TO *]"],
        "fl": "halId_s,title_s",
        "rows": 2,
        "sort": "producedDate_tdate desc",
        "wt": "json",
    }

    assert result["num_found"] == 42
    assert result["total_returned"] == 2
    assert result["has_more"] is True
    assert result["fields"] == ["halId_s", "title_s"]
    assert result["docs"] == [{"halId_s": "hal-1", "title_s": ["T"]}, {"halId_s": "hal-2"}]

    verification = parse_qs(urlparse(result["verification_url"]).query)
    assert verification["q"] == ["title_t:climat"]
    assert verification["fq"] == ["docType_s:ART", "producedDateY_i:[2020 TO *]"]
    assert verification["sort"] == ["producedDate_tdate desc"]


async def test_search_documents_defaults(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    result = await search_documents(q="")

    params = client.calls[0]["params"]
    assert params["q"] == "*:*"
    assert params["fl"] == ",".join(DEFAULT_FIELDS)
    assert "sort" not in params
    assert result["has_more"] is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rows": 0},
        {"rows": 101},
        {"fq": [f"docType_s:ART{i}" for i in range(21)]},
        {"q": "{!join from=a to=b}x"},
        {"fq": ["{!frange l=0}docid"]},
        {"fl": ["*"]},
        {"sort": "bad"},
    ],
)
async def test_search_documents_rejects_invalid_input_without_calling_hal(fake_httpx, kwargs):
    client = fake_httpx(json_data={})

    result = await search_documents(**kwargs)

    assert "error" in result
    assert result["query_url"] is None
    assert client.calls == []


async def test_search_documents_propagates_rejected_query(fake_httpx):
    fake_httpx(json_data={"error": {"msg": "Error. See help : /docs"}})

    result = await search_documents(q="notAField:1")

    assert "rejeté" in result["error"]
