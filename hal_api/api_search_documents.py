import re

from hal_api.client import SEARCH_URL, documents_url, hal_get

# Provisional default field list, to be refined.
DEFAULT_FIELDS = (
    "docid",
    "halId_s",
    "uri_s",
    "label_s",
    "title_s",
    "authFullName_s",
    "producedDateY_i",
    "docType_s",
    "doiId_s",
)

MAX_ROWS = 100
MAX_FQ = 20

FIELD_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
SORT_CLAUSE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s+(asc|desc)$")


def normalize_fields(fields: list[str] | None) -> list[str]:
    """
    Return the list of fields to request (`fl`): DEFAULT_FIELDS when `fields`
    is None or empty, otherwise the given names stripped and de-duplicated in
    order. Raises ValueError on anything that is not a plain field name
    (wildcards, functions and pseudo-fields such as `[docid]` are refused).
    """
    if not fields:
        return list(DEFAULT_FIELDS)
    cleaned = list(dict.fromkeys(f.strip() for f in fields if f and f.strip()))
    invalid = [f for f in cleaned if not FIELD_PATTERN.match(f)]
    if invalid:
        raise ValueError(f"Nom(s) de champ invalide(s) dans fl : {invalid} (ex. attendus : halId_s, title_s)")
    return cleaned or list(DEFAULT_FIELDS)


def normalize_sort(sort: str | None) -> str | None:
    """
    Return a canonical Solr `sort` string ("field dir, field dir"), or None
    when no sort is given (relevance order). Raises ValueError unless every
    comma-separated clause is `<field> asc|desc`; function sorts are refused.
    """
    if not sort or not sort.strip():
        return None
    clauses = []
    for raw in sort.split(","):
        match = SORT_CLAUSE_PATTERN.match(raw.strip())
        if not match:
            raise ValueError(
                f"Clause de tri invalide : {raw.strip()!r} (forme attendue : '<champ> asc' ou '<champ> desc', "
                "ex. 'producedDate_tdate desc')"
            )
        clauses.append(f"{match.group(1)} {match.group(2)}")
    return ", ".join(clauses)


def check_query(value: str, name: str) -> None:
    """
    Raise ValueError if `value` contains Solr local parameters (`{!...}`),
    which could switch the query parser (join, frange...) and are outside the
    scope of this generic search.
    """
    if "{!" in value:
        raise ValueError(f"Les paramètres locaux Solr ({{!...}}) ne sont pas autorisés dans {name}")


async def search_documents(
    q: str = "*:*",
    fq: list[str] | None = None,
    sort: str | None = None,
    rows: int = 20,
    fl: list[str] | None = None,
) -> dict:
    """
    Run a restricted query against HAL `/search/`: only q, fq, sort, rows and
    fl are forwarded; no facets, no pagination (`start`/`cursorMark`), JSON
    output forced by `hal_get`. Inputs are validated before any HTTP call.

    Returns:
        {"num_found", "total_returned", "has_more", "fields", "docs",
         "verification_url", "query_url"} on success, where `docs` are the HAL
        documents exactly as returned (keys = requested HAL field names, absent
        when the document has no value for that field);
        {"error": str, "query_url": str | None} otherwise.
    """
    q = (q or "").strip() or "*:*"
    fq_list = [f.strip() for f in (fq or []) if f and f.strip()]

    try:
        if not 1 <= rows <= MAX_ROWS:
            raise ValueError(f"rows doit être compris entre 1 et {MAX_ROWS}")
        if len(fq_list) > MAX_FQ:
            raise ValueError(f"Au plus {MAX_FQ} filtres fq")
        check_query(q, "q")
        for f in fq_list:
            check_query(f, "fq")
        fields = normalize_fields(fl)
        sort_clause = normalize_sort(sort)
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    params = {"q": q, "fq": fq_list, "fl": ",".join(fields), "rows": rows}
    if sort_clause:
        params["sort"] = sort_clause

    result = await hal_get(SEARCH_URL, params)
    if "error" in result:
        return result

    response_block = result["data"].get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))

    return {
        "num_found": num_found,
        "total_returned": len(docs),
        "has_more": num_found > len(docs),
        "fields": fields,
        "docs": docs,
        "verification_url": documents_url(fq_list, q=q, sort=sort_clause),
        "query_url": result["query_url"],
    }
