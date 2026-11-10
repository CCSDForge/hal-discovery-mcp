from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

import server
from hal_api.network import (
    build_network,
    cooccurrences,
    decode_query,
    encode_query,
    filter_network,
    vosviewer_json,
)

QUERY = "SELECT DISTINCT ?doc ?item ?label WHERE { ?doc dcterms:creator/hal:person ?item }"

ROWS = [
    {"doc": "d1", "item": "http://x/a", "label": "A"},
    {"doc": "d1", "item": "http://x/b", "label": "B"},
    {"doc": "d1", "item": "http://x/c", "label": "C"},
    {"doc": "d2", "item": "http://x/a", "label": "A"},
    {"doc": "d2", "item": "http://x/b", "label": "B"},
    {"doc": "d3", "item": "http://x/a", "label": "A."},
    {"doc": "d3", "item": "http://x/a", "label": "A"},
]


def sparql_json(rows, vars_=("doc", "item", "label")):
    return {
        "head": {"vars": list(vars_)},
        "results": {"bindings": [{k: {"value": v} for k, v in r.items()} for r in rows]},
    }


def test_cooccurrences_counts_documents_once_per_item():
    network = cooccurrences(ROWS)

    assert network["num_docs"] == 3
    assert network["weights"] == {"http://x/a": 3, "http://x/b": 2, "http://x/c": 1}
    assert network["links"][("http://x/a", "http://x/b")] == 2
    assert network["links"][("http://x/a", "http://x/c")] == 1
    assert network["labels"]["http://x/a"] == "A"


def test_label_defaults_to_last_iri_segment():
    network = cooccurrences([{"doc": "d", "item": "https://data.archives-ouvertes.fr/author/jean-dupont"}])

    assert network["labels"]["https://data.archives-ouvertes.fr/author/jean-dupont"] == "jean-dupont"


def test_filter_network_keeps_items_above_threshold_and_their_links():
    kept, links = filter_network(cooccurrences(ROWS), min_docs=2)

    assert kept == ["http://x/a", "http://x/b"]
    assert links == [(("http://x/a", "http://x/b"), 2)]


def test_vosviewer_json_format():
    network = cooccurrences(ROWS)
    kept, links = filter_network(network, min_docs=1)

    data = vosviewer_json(network, kept, links)

    items = data["network"]["items"]
    assert items[0] == {"id": 1, "label": "A", "url": "http://x/a", "weights": {"Documents": 3}}
    assert {"source_id": 1, "target_id": 2, "strength": 2} in data["network"]["links"]


def test_encode_decode_round_trip():
    assert decode_query(encode_query(QUERY + " é")) == QUERY + " é"


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        decode_query("pas-une-requete")


async def test_build_network_returns_summary_and_vosviewer_link(fake_httpx):
    fake_httpx(json_data=sparql_json(ROWS))

    result = await build_network(QUERY, min_docs=2)

    assert result["num_docs"] == 3
    assert result["num_items"] == 3
    assert result["num_items_kept"] == 2
    assert result["top_items"][0] == {"item": "http://x/a", "label": "A", "docs": 3}
    assert result["top_links"] == [{"source": "A", "target": "B", "docs": 2}]
    assert "warnings" not in result

    json_url = parse_qs(urlparse(result["vosviewer_url"]).query)["json"][0]
    assert json_url == result["network_json_url"]
    params = parse_qs(urlparse(json_url).query)
    assert decode_query(params["q"][0]) == QUERY
    assert params["min"] == ["2"]


async def test_build_network_warns_when_virtuoso_limit_is_reached(fake_httpx):
    fake_httpx(json_data=sparql_json(ROWS))

    result = await build_network(QUERY + " LIMIT 7", min_docs=1)

    assert any("tronqué" in w for w in result["warnings"])


async def test_build_network_requires_doc_and_item(fake_httpx):
    fake_httpx(json_data=sparql_json([{"x": "1"}], vars_=("x",)))

    result = await build_network("SELECT ?x WHERE { ?x ?p ?o }")

    assert "?doc" in result["error"]


async def test_build_network_rejects_ask(fake_httpx):
    client = fake_httpx(json_data={})

    result = await build_network("ASK { ?s ?p ?o }")

    assert "error" in result
    assert client.calls == []


def test_network_json_route_returns_vosviewer_json_with_cors(fake_httpx):
    fake_httpx(json_data=sparql_json(ROWS))

    response = TestClient(server.app).get("/mcp/network.json", params={"q": encode_query(QUERY), "min": 2})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert [i["label"] for i in response.json()["network"]["items"]] == ["A", "B"]


@pytest.mark.parametrize(
    "params",
    [
        {"q": "garbage"},
        {"q": encode_query("DELETE WHERE { ?s ?p ?o }")},
        {"q": encode_query(QUERY), "min": "0"},
    ],
)
def test_network_json_route_rejects_invalid_requests(fake_httpx, params):
    client = fake_httpx(json_data={})

    response = TestClient(server.app).get("/mcp/network.json", params=params)

    assert response.status_code == 400
    assert response.headers["access-control-allow-origin"] == "*"
    assert client.calls == []
