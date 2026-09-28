import asyncio
from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_authors import search_authors as _search_author
from hal_api.api_get_author_affiliations import api_get_author_affiliations


@mcp.tool()
async def get_author_affiliations(
    author_name: str,
    rows: Annotated[int, Field(ge=1, le=500)] = 100,
):
    """
    get_author_affiliations - Recherche l'historique des affiliations d'un auteur dans HAL :
    les structures (laboratoires, universités, institutions...) auxquelles il a été
    rattaché, afin d'aider à retracer son évolution de carrière scientifique.

    UTILISER CET OUTIL lorsque l'utilisateur demande :
      - des informations sur les affiliations d'un auteur
      - l'historique des affiliations d'un auteur
      - le laboratoire, l'université ou la structure de rattachement d'un chercheur
      - l'évolution de carrière, le parcours scientifique d'un chercheur
      - "quel laboratoire ?", "quelle université ?", "où travaille ?" un auteur

    Attention : NE PAS utiliser cet outil pour rechercher les PUBLICATIONS d'un auteur
    (articles, thèses, communications, etc.). Utiliser l'outil dédié
    `search_author_publications`.
    L'outil get_author_affiliations retourne uniquement les relations auteur-structure/affiliation et non la liste des publications.

    Fonctionnement : identifie l'auteur (hal_id) via le référentiel auteurs HAL puis
    parcourt ses publications les plus récentes (au plus `rows`) et en extrait deux champs :
        - structPrimaryHasAuthIdHal_fs : affiliation principale déclarée par publication
        - structHasAuthIdHal_fs : toutes les structures associées (principales + secondaires + hiérarchie institutionnelle) — plus large, plus bruité
        Chaque structure est agrégée avec son nombre de publications et la première /
        dernière année (first_year / last_year) où elle apparaît, ce qui permet de
        reconstituer la chronologie.

    RÈGLES ANTI-HALLUCINATION (strictes) :
         - Ne rapporter que ce qui est présent dans primary_structures_by_frequency ou all_linked_structures_by_frequency. Jamais d'invention de nom, id ou période à partir de connaissances générales.
         - Pour une affiliation "principale"/"actuelle" : utiliser primary_structures_by_frequency (all_linked... est trop large/parent), en regardant last_year.
         - Ne jamais déduire une affiliation depuis un titre ou un résumé de publication.
         - Pas de notion d'"affiliation implicite" : une affiliation est présente dans les données ou inconnue.
         - Toujours formuler comme "structure apparaissant comme affiliation principale déclarée dans X publications (entre first_year et last_year)", jamais comme un fait certifié d'"affiliation actuelle".
         - Homonymes (plusieurs auteurs dans authors_found) : présenter séparément ou demander confirmation, ne jamais fusionner.
         - num_found = 0, pas d'affiliation, pas de hal_id, ou clé "error" dans affiliations_by_author : signaler tel quel, sans reconstruire ni estimer.
         - has_more = true : seules les publications les plus récentes ont été analysées ; les affiliations plus anciennes peuvent manquer.

    Liens de vérification (API HAL, cliquables) :
         - Pour chaque auteur, `verification_url` liste toutes ses publications.
         - Chaque structure porte un `verification_url` listant les publications où l'auteur
           y est rattaché ; son `numFound` est égal à `num_publications` si has_more = false,
           et peut être supérieur sinon (toutes les publications, pas seulement celles analysées).
         - Toujours fournir à l'utilisateur les liens des structures citées, recopiés tels quels,
           sans jamais les modifier ni en construire de nouveaux.

    Paramétrage :
        - author_name: nom de l'auteur à rechercher (ex: "Jean Dupont")
        - rows: nombre max de publications analysées par auteur (1 à 500, défaut: 100)

    Returns:
        authors_found: [{name, hal_id, docid, validation_status}, ...]
        homonyms_warning: présent si plusieurs auteurs correspondent au nom
        affiliations_by_author: {
            hal_id: {
                num_found, total_returned, has_more, raw_fields_sample,
                primary_structures_by_frequency, all_linked_structures_by_frequency,
                verification_url, query_url
            }
            # chaque structure : {struct_id, struct_name, num_publications, first_year, last_year,
            #                     verification_url}
            # ou {"error": "..."} en cas d'échec pour cet auteur
        }
        query_url_author_search: URL utilisée pour identifier l'auteur dans HAL
    """
    if not author_name or not author_name.strip():
        return {"error": "Le paramètre 'author_name' est requis et ne peut pas être vide", "query_url": None}

    author_result = await _search_author(author_name.strip())
    if "error" in author_result:
        return author_result

    authors = author_result["authors"]

    if not authors:
        return {
            "authors_found": [],
            "message": f"Aucun auteur trouvé pour '{author_name}' dans HAL.",
            "query_url_author_search": author_result["query_url"],
        }

    response = {
        "authors_found": authors,
        "query_url_author_search": author_result["query_url"],
    }

    if len(authors) > 1:
        response["homonyms_warning"] = (
            f"{len(authors)} auteurs correspondent à '{author_name}'. "
            f"Vérifie avec l'utilisateur de qui il s'agit avant de conclure, "
            f"ou présente les affiliations séparément pour chaque personne."
        )

    affiliations_by_author = {}
    with_hal_id = []
    for idx, author in enumerate(authors):
        hal_id = author.get("hal_id")
        if hal_id:
            # Le référentiel renvoie une ligne par forme auteur : un même
            # hal_id peut apparaître plusieurs fois, on ne l'interroge qu'une fois.
            if hal_id not in with_hal_id:
                with_hal_id.append(hal_id)
        else:
            # Ne jamais ignorer silencieusement un auteur sans hal_id : une
            # entrée d'erreur explicite, distincte d'un "aucune affiliation
            # trouvée", évite que le LLM confonde "données absentes" et
            # "erreur technique".
            fallback_key = author.get("name") or f"unknown_author_{idx}"
            affiliations_by_author[fallback_key] = {
                "error": (
                    "Aucun hal_id disponible pour cet auteur (champ 'hal_id' "
                    "manquant ou vide dans les résultats de recherche). "
                    "Les affiliations n'ont pas pu être récupérées."
                )
            }

    results = await asyncio.gather(
        *(api_get_author_affiliations(id_hal=hal_id, rows=rows) for hal_id in with_hal_id)
    )
    affiliations_by_author.update(zip(with_hal_id, results))

    response["affiliations_by_author"] = affiliations_by_author

    return response