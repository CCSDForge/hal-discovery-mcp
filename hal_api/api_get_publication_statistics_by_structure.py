from hal_api.client import SEARCH_URL, documents_url, escape_phrase, hal_get

PIVOT = "producedDateY_i,docType_s"


def build_verification_urls(base_fq: list[str], stats: dict) -> dict:
    """
    Liens listant les publications derrière chaque chiffre : toute la période,
    chaque année et chaque type de document présents dans `stats`. Pas de lien
    par couple (année, type) : trop nombreux pour une grande structure.
    """
    doc_types = sorted({t for types in stats.values() for t in types})
    return {
        "all": documents_url(base_fq),
        "by_year": {
            year: documents_url([base_fq[0], f"producedDateY_i:{int(year)}"])
            for year in stats
        },
        "by_doc_type": {
            doc_type: documents_url(base_fq + [f'docType_s:"{escape_phrase(doc_type)}"'])
            for doc_type in doc_types
        },
    }


async def search_publication_stats(
    struct_id: int,
    start_year: int,
    end_year: int,
) -> dict:
    """
    Compte les publications d'une structure sur une période, par année de
    production et par type de document.

    Le comptage est fait par Solr (facette pivot) : aucune publication n'est
    rapatriée et les chiffres sont exacts quel que soit le volume.

    Returns:
        dict avec:
            - num_found (int): nombre total de publications correspondantes
            - stats (dict): {année: {type_document: nombre}}, années croissantes
            - verification_urls (dict): voir build_verification_urls
            - query_url (str): requête de comptage réellement envoyée
        ou en cas d'erreur:
            - error (str)
            - query_url (str | None)
    """
    base_fq = [
        f"structId_i:{int(struct_id)}",
        f"producedDateY_i:[{int(start_year)} TO {int(end_year)}]",
    ]
    params = {
        "q": "*:*",
        "fq": base_fq,
        "rows": 0,
        "facet": "true",
        "facet.pivot": PIVOT,
        "facet.limit": -1,
        "facet.mincount": 1,
    }

    result = await hal_get(SEARCH_URL, params)
    if "error" in result:
        return result

    data = result["data"]
    num_found = data.get("response", {}).get("numFound", 0)
    pivot = data.get("facet_counts", {}).get("facet_pivot", {}).get(PIVOT, [])

    stats = {}
    for year_entry in sorted(pivot, key=lambda e: e["value"]):
        stats[year_entry["value"]] = {
            type_entry["value"]: type_entry["count"]
            for type_entry in year_entry.get("pivot", [])
        }

    return {
        "num_found": num_found,
        "stats": stats,
        "verification_urls": build_verification_urls(base_fq, stats),
        "query_url": result["query_url"],
    }
