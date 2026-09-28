from urllib.parse import parse_qs, urlparse

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


async def test_api_get_author_affiliations_aggregates_structures_with_years(fake_httpx):
    id_hal = "yutong-fei"
    docs = [
        {
            "docid": 1,
            "producedDateY_i": 2023,
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
            "producedDateY_i": 2019,
            "structPrimaryHasAuthIdHal_fs": [
                make_entry("111", "Lab A", id_hal, "Yutong Fei"),
                # doublon dans la même publication : compté une seule fois
                make_entry("111", "Lab A", id_hal, "Yutong Fei"),
            ],
            "structHasAuthIdHal_fs": [make_entry("111", "Lab A", id_hal, "Yutong Fei")],
        },
    ]
    client = fake_httpx(json_data={"response": {"numFound": 2, "docs": docs}})

    result = await api_get_author_affiliations(id_hal, rows=100)

    assert result["num_found"] == 2
    assert result["total_returned"] == 2
    assert result["has_more"] is False
    assert "raw_docs" not in result
    assert result["raw_fields_sample"] == list(docs[0].keys())
    primary = result["primary_structures_by_frequency"]
    primary_url = primary[0].pop("verification_url")
    assert primary == [
        {"struct_id": "111", "struct_name": "Lab A", "num_publications": 2, "first_year": 2019, "last_year": 2023}
    ]
    all_by_freq = {s["struct_id"]: s["num_publications"] for s in result["all_linked_structures_by_frequency"]}
    assert all_by_freq == {"111": 2, "999": 1}
    assert client.calls[0]["params"]["sort"] == "producedDate_tdate desc"

    # Lien par structure : publications de CET auteur rattachées à CETTE structure.
    params = parse_qs(urlparse(primary_url).query)
    assert params["q"] == ['authIdHal_s:"yutong-fei"']
    assert params["fq"] == ["structPrimaryHasAuthIdHal_fs:111_FacetSep_*_JoinSep_yutong\\-fei_FacetSep_*"]
    linked_url = result["all_linked_structures_by_frequency"][0]["verification_url"]
    assert parse_qs(urlparse(linked_url).query)["fq"][0].startswith("structHasAuthIdHal_fs:")

    author_params = parse_qs(urlparse(result["verification_url"]).query)
    assert author_params["q"] == ['authIdHal_s:"yutong-fei"']
    assert "fq" not in author_params


async def test_api_get_author_affiliations_returns_empty_lists_without_docs(fake_httpx):
    fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    result = await api_get_author_affiliations("unknown-author")

    assert result["raw_fields_sample"] == []
    assert result["primary_structures_by_frequency"] == []


async def test_api_get_author_affiliations_returns_error_on_non_200(fake_httpx):
    fake_httpx(status_code=503, text_data="")

    result = await api_get_author_affiliations("yutong-fei")

    assert "503" in result["error"]