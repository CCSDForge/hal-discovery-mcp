from datetime import date

from hal_api.client import SEARCH_URL, date_range, documents_url, doi_url, escape_phrase, first, hal_get

FIELDS = (
    "halId_s,uri_s,title_s,abstract_s,producedDateY_i,producedDate_s,"
    "docType_s,doiId_s,authFullName_s"
)


def build_author_query(author_name: str | None, hal_id: str | None) -> str:
    """
    Requête Solr ciblant l'auteur (et non une recherche plein texte, qui
    remonterait aussi les publications qui mentionnent simplement le nom).
    L'identifiant HAL est prioritaire : il ne souffre pas des homonymes.
    """
    if hal_id:
        return f'authIdHal_s:"{escape_phrase(hal_id)}"'
    return f'authFullName_t:"{escape_phrase(author_name)}"'


async def search_author_publications(
    author_name: str | None = None,
    hal_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    rows: int = 50,
) -> dict:
    """
    Récupère les publications d'un auteur, les plus récentes d'abord.

    start_date / end_date : bornes incluses sur la date de production.

    Returns:
        dict avec num_found, total_returned, has_more, publications, query_url
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    params = {
        "q": build_author_query(author_name, hal_id),
        "fl": FIELDS,
        "rows": rows,
        "sort": "producedDate_tdate desc",
    }
    fq = date_range(start_date, end_date, "producedDate_tdate")
    if fq:
        params["fq"] = fq

    result = await hal_get(SEARCH_URL, params)
    if "error" in result:
        return result

    response_block = result["data"].get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))

    publications = [
        {
            "hal_id": d.get("halId_s"),
            "url": d.get("uri_s"),
            "title": first(d.get("title_s")),
            # None si HAL ne fournit pas de résumé (jamais de texte de substitution).
            "abstract": first(d.get("abstract_s")) or None,
            "year": d.get("producedDateY_i"),
            "date": d.get("producedDate_s"),
            "type": d.get("docType_s"),
            "doi": d.get("doiId_s"),
            "doi_url": doi_url(d.get("doiId_s")),
            "authors": d.get("authFullName_s") or [],
        }
        for d in docs
    ]

    return {
        "num_found": num_found,
        "total_returned": len(publications),
        "has_more": num_found > len(publications),
        "publications": publications,
        "verification_url": documents_url([fq] if fq else [], q=params["q"]),
        "query_url": result["query_url"],
    }
