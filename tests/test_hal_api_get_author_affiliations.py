import json

from hal_api.api_get_author_affiliations import (
    _parse_struct_auth_entry,
    api_get_author_affiliations,
)


def make_entry(struct_id, struct_name, hal_id, auth_name):
    return f"{struct_id}_FacetSep_{struct_name}_JoinSep_{hal_id}_FacetSep_{auth_name}"


def test_parse_struct_auth_entry_parses_well_formed_entry():
    entry = make_entry("194495", "Universite Claude Bernard Lyon 1", "yutong-fei", "Yutong Fei")

    parsed = _parse_struct_auth_entry(entry)

    assert parsed == {
        "struct_id": "194495",
        "struct_name": "Universite Claude Bernard Lyon 1",
        "hal_id": "yutong-fei",
        "auth_full_name": "Yutong Fei",
    }


def test_parse_struct_auth_entry_returns_none_for_empty_or_missing_entry():
    assert _parse_struct_auth_entry("") is None
    assert _parse_struct_auth_entry(None) is None


def test_parse_struct_auth_entry_returns_none_without_join_sep():
    assert _parse_struct_auth_entry("194495_FacetSep_Lyon 1") is None


def test_parse_struct_auth_entry_returns_none_when_left_or_right_missing_facet_sep():
    assert _parse_struct_auth_entry("194495_JoinSep_yutong-fei_FacetSep_Yutong Fei") is None
    assert _parse_struct_auth_entry("194495_FacetSep_Lyon 1_JoinSep_yutong-fei") is None


async def test_api_get_author_affiliations_aggregates_primary_and_all_structures(fake_aiohttp):
    id_hal = "yutong-fei"
    docs = [
        {
            "docid": 1,
            "structPrimaryHasAuthIdHal_fs": [
                make_entry("111", "Lab A", id_hal, "Yutong Fei"),
                # co-auteur : ne doit pas être compté pour id_hal
                make_entry("222", "Lab B", "other-author", "Other Author"),
            ],
            "structHasAuthIdHal_fs": [
                make_entry("111", "Lab A", id_hal, "Yutong Fei"),
                make_entry("999", "Parent Institution", id_hal, "Yutong Fei"),
            ],
        },
        {
            "docid": 2,
            "structPrimaryHasAuthIdHal_fs": [make_entry("111", "Lab A", id_hal, "Yutong Fei")],
            "structHasAuthIdHal_fs": [make_entry("111", "Lab A", id_hal, "Yutong Fei")],
        },
    ]
    body = json.dumps({"response": {"numFound": 2, "docs": docs}})
    fake_aiohttp(text_data=body)

    result = await api_get_author_affiliations(id_hal, rows=100)

    assert result["num_found"] == 2
    assert result["total_returned"] == 2
    assert result["has_more"] is False
    assert result["raw_fields_sample"] == list(docs[0].keys())
    assert result["primary_structures_by_frequency"] == [
        {"struct_id": "111", "struct_name": "Lab A", "num_publications": 2}
    ]
    all_by_freq = {s["struct_id"]: s["num_publications"] for s in result["all_linked_structures_by_frequency"]}
    assert all_by_freq == {"111": 2, "999": 1}


async def test_api_get_author_affiliations_returns_empty_raw_fields_sample_without_docs(fake_aiohttp):
    body = json.dumps({"response": {"numFound": 0, "docs": []}})
    fake_aiohttp(text_data=body)

    result = await api_get_author_affiliations("unknown-author")

    assert result["raw_fields_sample"] == []
    assert result["primary_structures_by_frequency"] == []


async def test_api_get_author_affiliations_returns_error_on_non_200(fake_aiohttp):
    fake_aiohttp(status=503, text_data="")

    result = await api_get_author_affiliations("yutong-fei")

    assert "503" in result["error"]


async def test_api_get_author_affiliations_detects_html_response(fake_aiohttp):
    fake_aiohttp(status=200, text_data="<!DOCTYPE html><html><body>oops</body></html>")

    result = await api_get_author_affiliations("yutong-fei")

    assert "HTML" in result["error"]


async def test_api_get_author_affiliations_returns_error_on_invalid_json(fake_aiohttp):
    fake_aiohttp(status=200, text_data="not json at all")

    result = await api_get_author_affiliations("yutong-fei")

    assert "error" in result
