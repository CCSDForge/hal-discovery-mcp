from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_lab_keyword_statistics import search_lab_keywords


@mcp.tool()
async def search_lab_keyword_statistics(
    struct_id: int,
    year: int,
    limit: Annotated[int, Field(ge=1, le=200)] = 30,
) -> dict:
    """
    search_lab_keyword_statistics - Analyse les thématiques de recherche d'une structure enregistrée dans HAL à partir de la distribution des mots-clés de ses publications.

    UTILISER CET OUTIL lorsque l'utilisateur souhaite :
      - identifier les thématiques de recherche ou les thématiques émergentes d'une structure ;
      - connaître les mots-clés les plus fréquents des publications d'une structure pour une année donnée ;
      - analyser les principaux sujets de recherche d'un laboratoire, d'une université ou d'une institution.

    IMPORTANT :
      - Cet outil ne retourne PAS la liste des publications.
      - Les statistiques sont calculées directement par Solr à l'aide des facettes (`facet`).
      - Le champ `keyword_aggregation` contient déjà les fréquences des mots-clés.
      - Le LLM ne doit effectuer aucun comptage ou recalcul des occurrences.
      - Les mots-clés sont ceux saisis par les déposants, sans normalisation : des
        variantes (casse, langue, singulier/pluriel) peuvent apparaître séparément.

    Workflow :
      1. Si l'utilisateur fournit uniquement le nom ou l'acronyme d'une structure,
         utiliser d'abord `search_structures` afin de récupérer son identifiant HAL (`id`).
      2. Appeler ensuite cet outil avec cet identifiant comme `struct_id` et l'année souhaitée.

    Parameters:
        - struct_id: Identifiant HAL de la structure de recherche.
        - year: Année de production des publications à analyser.
        - limit: Nombre maximal de mots-clés à retourner (1 à 200, par défaut : 30).

    Returns:
        - struct_id: Identifiant HAL de la structure analysée.
        - year: Année analysée.
        - total_publications: Nombre total de publications de la structure pour cette année.
        - keyword_aggregation: Agrégation des mots-clés, sous la forme :
            `{mot_clé: nombre_d'occurrences}`,
            classés par fréquence décroissante.
        - verification_urls: Liens cliquables vers l'API HAL listant les publications
            derrière les chiffres :
              * `all` : toutes les publications de la structure pour l'année ;
              * `by_keyword` : `{mot_clé: lien}`, pour les 30 premiers mots-clés au plus.
            Dans chaque lien, `numFound` en tête de la réponse est le nombre exact ;
            seules les 100 publications les plus récentes sont listées.
        - query_url: URL de la requête de comptage envoyée à l'API HAL.

    Présentation des résultats :
      - Toujours fournir le lien `verification_urls.all`, et les liens `by_keyword` des
        mots-clés cités dans la réponse.
      - Recopier les liens tels quels, sans jamais les modifier ni en construire de nouveaux.
    """
    return await search_lab_keywords(struct_id, year, limit=limit)