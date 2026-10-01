from hal_api.api_search_structures import (
    _to_structure,
    hal_api_get_structure_by_id,
    hal_api_get_structures_by_ids,
    hal_api_search_structure,
)


def make_doc(docid, label, acronym=None, type_s=None, parent_ids=None, parent_names=None, valid="VALID"):
    doc = {
        "docid": docid,
        "label_s": label,
        "acronym_s": acronym,
        "type_s": type_s,
        "valid_s": valid,
    }
    # Comme HAL : champs multivalués absents quand il n'y a pas de parent.
    if parent_ids:
        doc["parentDocid_i"] = parent_ids
        doc["parentName_s"] = parent_names
    return doc


def test_to_structure_maps_hal_fields_to_stable_keys():
    doc = make_doc(
        700, "CREATIS", acronym="CREATIS", type_s="laboratory",
        parent_ids=["194495", "210962"], parent_names=["Lyon 1", "CPE Lyon"],
    )

    structure = _to_structure(doc)

    assert structure == {
        "id": 700,
        "name": "CREATIS",
        "acronym": "CREATIS",
        "type": "laboratory",
        "parent_ids": ["194495", "210962"],
        "parent_names": ["Lyon 1", "CPE Lyon"],
        "validation_status": "VALID",
    }


def test_to_structure_without_parents_returns_empty_lists():
    structure = _to_structure(make_doc(194495, "Lyon 1"))

    assert structure["parent_ids"] == []
    assert structure["parent_names"] == []


async def test_hal_api_search_structure_splits_by_validation_status(fake_httpx):
    docs = [
        make_doc(1, "Valid Lab", valid="VALID"),
        make_doc(2, "Incoming Lab", valid="INCOMING"),
        make_doc(3, "Legacy Lab", valid="OLD"),
    ]
    fake_httpx(json_data={"response": {"numFound": 3, "docs": docs}})

    result = await hal_api_search_structure("Lab", rows=10)

    assert result["num_found"] == 3
    assert [s["id"] for s in result["structures_valid"]] == [1]
    assert [s["id"] for s in result["structures_incoming"]] == [2]
    assert [s["id"] for s in result["structures_other_status"]] == [3]
    assert result["query_url"]
    assert result["verification_url"] == result["query_url"]


async def test_hal_api_search_structure_escapes_quotes(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    await hal_api_search_structure('Lab "X"')

    assert client.calls[0]["params"]["q"] == 'text:"Lab \\"X\\""'


async def test_hal_api_search_structure_returns_error_on_non_200(fake_httpx):
    fake_httpx(status_code=500)

    result = await hal_api_search_structure("Lab")

    assert "500" in result["error"]


async def test_hal_api_get_structures_by_ids_resolves_in_one_request(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 2, "docs": [
        make_doc("1005874", "URFIST", acronym="URFIST de Lyon"),
        make_doc("154357", "URFIST", acronym="URFIST Paris"),
    ]}})

    result = await hal_api_get_structures_by_ids([1005874, 154357, 999])

    assert set(result["structures"]) == {1005874, 154357}
    assert result["structures"][154357]["acronym"] == "URFIST Paris"
    assert client.calls[0]["params"]["q"] == "docid:(1005874 OR 154357 OR 999)"
    assert len(client.calls) == 1


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
