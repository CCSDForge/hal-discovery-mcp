from hal_api.api_search_structures import (
    _to_structure,
    hal_api_get_structure_by_id,
    hal_api_search_structure,
)


def make_doc(docid, label, acronym=None, type_s=None, parent_docid=None, parent_name=None, valid="VALID"):
    return {
        "docid": docid,
        "label_s": label,
        "acronym_s": acronym,
        "type_s": type_s,
        "parentDocid_s": parent_docid,
        "parentName_s": parent_name,
        "valid_s": valid,
    }


def test_to_structure_maps_hal_fields_to_stable_keys():
    doc = make_doc(194495, "Universite Claude Bernard Lyon 1", acronym="UCBL", valid="VALID")

    structure = _to_structure(doc)

    assert structure == {
        "id": 194495,
        "nom": "Universite Claude Bernard Lyon 1",
        "sigle": "UCBL",
        "type": None,
        "id_parent": None,
        "nom_parent": None,
        "statut_validation": "VALID",
    }


async def test_hal_api_search_structure_splits_by_validation_status(fake_httpx):
    docs = [
        make_doc(1, "Valid Lab", valid="VALID"),
        make_doc(2, "Incoming Lab", valid="INCOMING"),
        make_doc(3, "Legacy Lab", valid="OLD"),
    ]
    fake_httpx(json_data={"response": {"numFound": 3, "docs": docs}})

    result = await hal_api_search_structure("Lab", rows=10)

    assert result["num_found"] == 3
    assert [s["id"] for s in result["structures_valides"]] == [1]
    assert [s["id"] for s in result["structures_incoming"]] == [2]
    assert [s["id"] for s in result["structures_autres_statuts"]] == [3]
    assert result["query_url"]


async def test_hal_api_search_structure_returns_error_on_non_200(fake_httpx):
    fake_httpx(status_code=500)

    result = await hal_api_search_structure("Lab")

    assert "500" in result["error"]


async def test_hal_api_get_structure_by_id_found(fake_httpx):
    fake_httpx(json_data={"response": {"numFound": 1, "docs": [make_doc(194495, "Lyon 1")]}})

    result = await hal_api_get_structure_by_id(194495)

    assert result["found"] is True
    assert result["structure"]["id"] == 194495


async def test_hal_api_get_structure_by_id_not_found(fake_httpx):
    fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    result = await hal_api_get_structure_by_id(0)

    assert result["found"] is False
    assert result["structure"] is None


async def test_hal_api_get_structure_by_id_returns_error_on_non_200(fake_httpx):
    fake_httpx(status_code=404)

    result = await hal_api_get_structure_by_id(194495)

    assert "404" in result["error"]
