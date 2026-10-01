from hal_api.client import SEARCH_URL, documents_url, escape_phrase, hal_get

# Au-delà, on ne fournit pas de lien par mot-clé (trop de tokens pour le LLM).
MAX_KEYWORD_URLS = 30


async def search_lab_keywords(
    struct_id: int,
    year: int,
    limit: int = 30,
) -> dict:
    """
    Recherche les mots-clés agrégés d'une structure HAL pour une année.

    Solr effectue directement le comptage via les facettes : aucune
    publication n'est rapatriée.
    """
    base_fq = [
        f"structId_i:{int(struct_id)}",
        f"producedDateY_i:{int(year)}",
    ]
    params = {
        "q": "*:*",
        "fq": base_fq,
        "facet": "true",
        "facet.field": "keyword_s",
        "facet.limit": limit,
        "facet.mincount": 1,
        "facet.sort": "count",
        "rows": 0,
    }

    result = await hal_get(SEARCH_URL, params)
    if "error" in result:
        return result

    data = result["data"]

    # Solr renvoie une liste à plat : ["mot1", 120, "mot2", 90, ...]
    facet_values = (
        data
        .get("facet_counts", {})
        .get("facet_fields", {})
        .get("keyword_s", [])
    )
    keyword_aggregation = dict(zip(facet_values[::2], facet_values[1::2]))

    return {
        "struct_id": struct_id,
        "year": year,
        "total_publications": data.get("response", {}).get("numFound", 0),
        "keyword_aggregation": keyword_aggregation,
        "verification_urls": {
            "all": documents_url(base_fq),
            "by_keyword": {
                keyword: documents_url(base_fq + [f'keyword_s:"{escape_phrase(keyword)}"'])
                for keyword in list(keyword_aggregation)[:MAX_KEYWORD_URLS]
            },
        },
        "query_url": result["query_url"],
    }
