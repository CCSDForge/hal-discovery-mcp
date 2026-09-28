from core.mcp import mcp
from hal_api.api_get_publication_statistics_by_structure import search_publication_stats


@mcp.tool()
async def get_publication_statistics_by_structure(
    struct_id: int,
    start_year: int,
    end_year: int,
):
    """
    Outil get_publication_statistics_by_structure - Récupère le nombre de publications HAL pour une structure et une
    période données, réparties par année et par type de document.

    Utiliser cet outil lorsque l'utilisateur souhaite connaître la production scientifique d'une structure (laboratoire,
    université, institution, etc.), notamment le nombre de publications par année et leur répartition par type de document.

    IMPORTANT :
    Cet outil nécessite l'identifiant HAL (`struct_id`) de la structure.
    Si l'utilisateur ne connaît que le nom ou l'acronyme de la structure,
    utiliser d'abord l'outil `search_structures` afin de récupérer son
    identifiant HAL (`id`), puis appeler cet outil avec cet identifiant.

    Les comptages sont calculés directement par HAL (facettes Solr) sur la
    totalité des publications : ils sont exacts et exhaustifs, sans troncature.
    L'année utilisée est l'année de production (producedDateY_i).

    Parameters:
        - struct_id: Identifiant HAL de la structure de recherche.
        - start_year: Année de début de la période d'analyse (incluse).
        - end_year: Année de fin de la période d'analyse (incluse). Doit être supérieure ou égale à `start_year`.

    Returns:
        - struct_id: Identifiant HAL de la structure analysée.
        - period: Période analysée au format "start_year-end_year".
        - num_found: Nombre total de publications correspondant aux critères dans HAL.
        - stats: Répartition des publications par année et par type de document, sous la forme :
            `{année: {type_document: nombre_de_publications}}`. Une année absente signifie 0 publication.
        - verification_urls: Liens cliquables vers l'API HAL listant les publications
            derrière les chiffres, pour que l'utilisateur puisse les vérifier :
              * `all` : toutes les publications de la période ;
              * `by_year` : `{année: lien}` ;
              * `by_doc_type` : `{type_document: lien}`, sur toute la période.
            Dans chaque lien, `numFound` en tête de la réponse est le nombre exact de
            publications ; seules les 100 plus récentes sont listées.
        - query_url: URL de la requête de comptage envoyée à l'API HAL, fournie à des fins de traçabilité.

    Présentation des résultats :
      - Toujours fournir à l'utilisateur le lien `verification_urls.all`, et les liens
        `by_year` / `by_doc_type` correspondant aux chiffres cités dans la réponse.
      - Recopier les liens tels quels, sans jamais les modifier ni en construire de nouveaux.
    """
    if start_year > end_year:
        return {"error": f"start_year ({start_year}) doit être <= end_year ({end_year})", "query_url": None}

    result = await search_publication_stats(
        struct_id=struct_id,
        start_year=start_year,
        end_year=end_year,
    )
    if "error" in result:
        return result

    return {
        "struct_id": struct_id,
        "period": f"{start_year}-{end_year}",
        "num_found": result["num_found"],
        "stats": result["stats"],
        "verification_urls": result["verification_urls"],
        "query_url": result["query_url"],
    }