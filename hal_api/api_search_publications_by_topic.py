import re

from hal_api.client import SEARCH_URL, doc_types_fq, documents_url, first, hal_get

# Types retenus par défaut : publications scientifiques (hors mémoires,
# posters, blogs, logiciels...).
DEFAULT_DOC_TYPES = ("ART", "COMM", "THESE", "OUV", "COUV")

ABSTRACT_MAX_CHARS = 600
MAX_AUTHORS = 10
MAX_KEYWORDS = 10
MAX_DOMAIN_FACETS = 10

FIELDS = (
    "halId_s,uri_s,title_s,authFullName_s,producedDateY_i,docType_s,doiId_s,"
    "journalTitle_s,conferenceTitle_s,bookTitle_s,keyword_s,abstract_s,language_s"
)
DOMAIN_LABEL_FIELD = "fr_domainAllCodeLabel_fs"

DOMAIN_PATTERN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*$")

SORTS = {
    "relevance": None,
    "date": "producedDate_tdate desc",
}


def build_topic_fq(
    start_year: int | None,
    end_year: int | None,
    doc_types: list[str],
    domain: str | None,
) -> list[str]:
    """
    Filtres Solr. Lève ValueError si un code de type ou de domaine n'a pas la
    forme attendue (ils sont insérés tels quels dans la requête).
    """
    fq = []
    if start_year is not None or end_year is not None:
        low = int(start_year) if start_year is not None else "*"
        high = int(end_year) if end_year is not None else "*"
        fq.append(f"producedDateY_i:[{low} TO {high}]")

    types_fq = doc_types_fq(doc_types)
    if types_fq:
        fq.append(types_fq)

    if domain:
        if not DOMAIN_PATTERN.match(domain):
            raise ValueError(f"Code de domaine invalide : {domain!r} (ex. attendus : shs, shs.info)")
        # domain_s indexe chaque niveau préfixé par sa profondeur : "0.shs",
        # "1.shs.info", "2.shs.info.comm". Filtrer ainsi inclut les sous-domaines.
        fq.append(f'domain_s:"{domain.count(".")}.{domain}"')

    return fq


def _truncate(text: str | None, max_chars: int) -> str | None:
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " […]"


def _to_publication(doc: dict) -> dict:
    authors = doc.get("authFullName_s") or []
    venue = doc.get("journalTitle_s") or doc.get("conferenceTitle_s") or doc.get("bookTitle_s")
    return {
        "hal_id": doc.get("halId_s"),
        "url": doc.get("uri_s"),
        "title": first(doc.get("title_s")),
        "authors": authors[:MAX_AUTHORS],
        "num_authors": len(authors),
        "year": doc.get("producedDateY_i"),
        "type": doc.get("docType_s"),
        "venue": first(venue),
        "doi": doc.get("doiId_s"),
        "keywords": (doc.get("keyword_s") or [])[:MAX_KEYWORDS],
        "abstract": _truncate(first(doc.get("abstract_s")), ABSTRACT_MAX_CHARS),
        "language": first(doc.get("language_s")),
    }


def _parse_domain_facet(values: list) -> list[dict]:
    """["shs.info_FacetSep_Sciences.../Sciences de l'information", 40, ...] -> [{code, label, count}]"""
    domains = []
    for raw, count in zip(values[::2], values[1::2]):
        code, _, label = raw.partition("_FacetSep_")
        domains.append({"code": code, "label": label or None, "count": count})
    return domains


def _pairs(values: list) -> dict:
    return dict(zip(values[::2], values[1::2]))


async def search_publications_by_topic(
    query: str,
    start_year: int | None = None,
    end_year: int | None = None,
    doc_types: list[str] | None = None,
    domain: str | None = None,
    sort: str = "relevance",
    rows: int = 20,
) -> dict:
    """
    Recherche des publications HAL sur un sujet (titre, résumé, mots-clés...).

    `query` est passée telle quelle à Solr : elle peut contenir des expressions
    entre guillemets et les opérateurs AND / OR / NOT, pour combiner synonymes
    et traductions.

    Returns:
        dict avec num_found, total_returned, has_more, publications, facets
        ({by_domain, by_doc_type, by_year}), verification_url, query_url
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    if sort not in SORTS:
        return {"error": f"sort doit valoir l'une de ces valeurs : {list(SORTS)}", "query_url": None}

    try:
        fq = build_topic_fq(start_year, end_year, list(doc_types or []), domain)
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    params = {
        "q": query,
        "fq": fq,
        "fl": FIELDS,
        "rows": rows,
        "facet": "true",
        "facet.field": [DOMAIN_LABEL_FIELD, "docType_s", "producedDateY_i"],
        "facet.mincount": 1,
        f"f.{DOMAIN_LABEL_FIELD}.facet.limit": MAX_DOMAIN_FACETS,
        "f.docType_s.facet.limit": -1,
        "f.producedDateY_i.facet.limit": -1,
        "f.producedDateY_i.facet.sort": "index",
    }
    if SORTS[sort]:
        params["sort"] = SORTS[sort]

    result = await hal_get(SEARCH_URL, params)
    if "error" in result:
        return result

    data = result["data"]
    response_block = data.get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))
    facet_fields = data.get("facet_counts", {}).get("facet_fields", {})

    return {
        "num_found": num_found,
        "total_returned": len(docs),
        "has_more": num_found > len(docs),
        "publications": [_to_publication(d) for d in docs],
        "facets": {
            "by_domain": _parse_domain_facet(facet_fields.get(DOMAIN_LABEL_FIELD, [])),
            "by_doc_type": _pairs(facet_fields.get("docType_s", [])),
            "by_year": _pairs(facet_fields.get("producedDateY_i", [])),
        },
        # Même tri que l'outil : le lien liste les publications dans le même ordre.
        "verification_url": documents_url(fq, q=query, sort=SORTS[sort]),
        "query_url": result["query_url"],
    }
