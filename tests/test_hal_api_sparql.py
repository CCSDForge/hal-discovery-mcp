import httpx
import pytest

from hal_api.api_sparql import MAX_LIMIT, sparql, validate_query
from hal_api.sparql_client import SPARQL_URL, sparql_get, with_prefixes


def sparql_json(vars_, rows):
    return {
        "head": {"vars": vars_},
        "results": {"bindings": [{k: {"type": "literal", "value": v} for k, v in r.items()} for r in rows]},
    }


# --- validate_query -------------------------------------------------------------------------

def test_select_without_limit_gets_default_limit():
    query, limit = validate_query("SELECT ?s WHERE { ?s ?p ?o }")

    assert query.endswith("LIMIT 100")
    assert limit == 100


def test_explicit_limit_is_kept():
    query, limit = validate_query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 20")

    assert query == "SELECT ?s WHERE { ?s ?p ?o } LIMIT 20"
    assert limit == 20


def test_limit_above_maximum_is_rejected():
    with pytest.raises(ValueError, match="LIMIT"):
        validate_query(f"SELECT ?s WHERE {{ ?s ?p ?o }} LIMIT {MAX_LIMIT + 1}")


def test_subquery_limit_does_not_count_as_main_limit():
    query, limit = validate_query("SELECT ?s WHERE { { SELECT ?s WHERE { ?s ?p ?o } LIMIT 5000 } }")

    assert limit == 100
    assert query.endswith("LIMIT 100")


def test_offset_is_rejected():
    with pytest.raises(ValueError, match="OFFSET"):
        validate_query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 10 OFFSET 10")


def test_prefixes_before_select_are_accepted():
    query, _ = validate_query("PREFIX ex: <http://example.org/> SELECT ?s WHERE { ?s ex:p ?o }")

    assert query.startswith("PREFIX ex:")


def test_ask_has_no_limit():
    query, limit = validate_query("ASK { ?s ?p ?o }")

    assert limit is None
    assert "LIMIT" not in query


@pytest.mark.parametrize(
    "query",
    [
        "INSERT DATA { <http://x> <http://y> <http://z> }",
        "DELETE WHERE { ?s ?p ?o }",
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
        "DESCRIBE <http://x>",
        "SELECT ?s WHERE { SERVICE <http://dbpedia.org/sparql> { ?s ?p ?o } }",
        "define sql:big-data-const 0 SELECT ?s WHERE { ?s ?p ?o }",
        "SELECT ?s WHERE { ?s ?p ?o } ; DELETE WHERE { ?s ?p ?o }",
    ],
)
def test_non_read_queries_are_rejected(query):
    with pytest.raises(ValueError):
        validate_query(query)


def test_virtuoso_functions_other_than_contains_are_rejected():
    with pytest.raises(ValueError, match="bif:file_to_string"):
        validate_query('SELECT (bif:file_to_string("/etc/passwd") AS ?x) WHERE { }')


def test_bif_contains_is_accepted():
    validate_query('SELECT ?d WHERE { ?d dc:subject ?t . ?t bif:contains "\\"open science\\"" }')


def test_forbidden_words_inside_literals_iris_and_comments_are_ignored():
    validate_query(
        'SELECT ?d WHERE { ?d dcterms:title ?t . FILTER(CONTAINS(?t, "delete insert drop")) '
        "?d <http://example.org/service> ?x . } # load clear"
    )


def test_unbalanced_braces_are_rejected():
    with pytest.raises(ValueError, match="Accolades"):
        validate_query("SELECT ?s WHERE { ?s ?p ?o ")


def test_empty_query_is_rejected():
    with pytest.raises(ValueError):
        validate_query("   ")


# --- with_prefixes --------------------------------------------------------------------------

def test_missing_prefixes_are_added_and_declared_ones_kept():
    query = with_prefixes("PREFIX hal: <http://autre/> SELECT ?s WHERE { ?s foaf:name ?n }")

    assert "PREFIX foaf: <http://xmlns.com/foaf/0.1/>" in query
    assert query.count("PREFIX hal:") == 1


# --- sparql_get -----------------------------------------------------------------------------

async def test_sparql_get_returns_simplified_rows(fake_httpx):
    client = fake_httpx(json_data=sparql_json(["s"], [{"s": "a"}, {"s": "b"}]))

    result = await sparql_get("SELECT ?s WHERE { ?s ?p ?o } LIMIT 2")

    assert result["rows"] == [{"s": "a"}, {"s": "b"}]
    assert result["vars"] == ["s"]
    assert client.calls[0]["url"] == SPARQL_URL
    assert "format=text%2Fhtml" in result["verification_url"]


async def test_sparql_get_reports_virtuoso_error_message(fake_httpx):
    fake_httpx(
        status_code=400,
        text_data="Virtuoso 37000 Error SP030: SPARQL compiler, line 2: syntax error\n\nSPARQL query:\n...",
        headers={"Content-Type": "text/plain"},
    )

    result = await sparql_get("SELECT ?s WHERE { ?s a }")

    assert "SP030" in result["error"]
    assert "400" in result["error"]


async def test_sparql_get_handles_timeout(fake_httpx):
    fake_httpx(raise_on_get=httpx.ReadTimeout("timeout"))

    result = await sparql_get("SELECT ?s WHERE { ?s ?p ?o }")

    assert "délai" in result["error"]
    assert result["query_url"] is None


# --- sparql ---------------------------------------------------------------------------------

async def test_sparql_returns_rows_and_markdown_block(fake_httpx):
    fake_httpx(json_data=sparql_json(["s"], [{"s": "a"}]))

    result = await sparql("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1")

    assert result["total_returned"] == 1
    assert result["limit_reached"] is True
    assert result["sparql_query"].startswith("PREFIX hal:")
    assert "```sparql" in result["sparql_queries"]
    assert result["verification_url"] in result["sparql_queries"]


async def test_sparql_truncates_long_values(fake_httpx):
    fake_httpx(json_data=sparql_json(["a"], [{"a": "x" * 5000}]))

    result = await sparql("SELECT ?a WHERE { ?d dcterms:abstract ?a }")

    assert len(result["rows"][0]["a"]) < 1100


async def test_sparql_ask_returns_boolean(fake_httpx):
    fake_httpx(json_data={"head": {}, "boolean": True})

    result = await sparql("ASK { ?s ?p ?o }")

    assert result["boolean"] is True


async def test_sparql_rejected_query_does_not_call_hal(fake_httpx):
    client = fake_httpx(json_data={})

    result = await sparql("DELETE WHERE { ?s ?p ?o }")

    assert "error" in result
    assert client.calls == []
