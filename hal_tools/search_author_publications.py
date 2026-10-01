from datetime import date
from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_author_publications import search_author_publications as _search_author_publications


@mcp.tool()
async def search_author_publications(
    author_name: str | None = None,
    hal_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    rows: Annotated[int, Field(ge=1, le=200)] = 50,
):
    """
        search_author_publications - Recherche les publications d'un auteur dans HAL,
        les plus récentes d'abord.

        Utiliser cet outil lorsque l'utilisateur souhaite consulter les publications
        d'un auteur, obtenir leurs métadonnées.

        Identification de l'auteur (au moins un des deux) :
            - `hal_id` (recommandé) : identifiant HAL obtenu via `search_authors`.
              Recherche exacte, sans risque de mélanger des homonymes.
            - `author_name` : nom complet tel qu'il apparaît dans les notices
              (ex. : "Yutong Fei"). Peut inclure des publications d'homonymes et
              manquer celles signées sous une autre forme du nom.
            Si les deux sont fournis, `hal_id` est utilisé.

        Parameters:
            author_name: Nom complet de l'auteur.
            hal_id: Identifiant HAL de l'auteur (ex. : "yutong-fei").
            start_date:
                Date de début de la période de recherche (incluse),
                au format YYYY-MM-DD, appliquée à la date de production.
                Si None, aucune borne inférieure n'est appliquée.
            end_date:
                Date de fin de la période de recherche (incluse),
                au format YYYY-MM-DD.
                Si None, aucune borne supérieure n'est appliquée.
            rows:
                Nombre maximal de publications à retourner
                (1 à 200, par défaut : 50).

        Returns:
            num_found:
                Nombre total de publications de l'auteur dans HAL pour ces critères.
            total_returned:
                Nombre de publications effectivement retournées.
            has_more:
                `True` si toutes les publications n'ont pas été retournées : ne pas
                présenter la liste comme exhaustive.
            with_abstract / without_abstract:
                Nombre de publications retournées avec / sans résumé.
            publications:
                Liste des publications, chacune avec : hal_id, url (lien vers la
                notice HAL), title, abstract (None si absent), year, date, type,
                doi (identifiant brut, None si absent), doi_url (lien
                https://doi.org/... vers la version éditeur, None si pas de DOI), authors.
            verification_url:
                Lien cliquable vers l'API HAL listant les publications de l'auteur pour
                ces critères (titre, lien HAL, date, type) ; `numFound` en tête de la
                réponse est égal à `num_found`.
            query_url:
                URL exacte de la requête envoyée à l'API HAL.

        Présentation des résultats (OBLIGATOIRE) :
            - Pour CHAQUE publication présentée, toujours afficher :
                * le lien HAL (`url`) ;
                * le DOI sous forme de lien (`doi_url`) lorsqu'il est présent. Si `doi_url`
                  vaut None, ne rien afficher pour le DOI : ne jamais en inventer ni en chercher un.
              Format conseillé :
                Auteurs (année). Titre. Type.
                HAL : <url> — DOI : <doi_url>
            - Recopier les liens tels quels, sans les modifier ni les raccourcir.
            - Toujours fournir aussi le lien `verification_url`.
        """
    author_name = (author_name or "").strip() or None
    hal_id = (hal_id or "").strip() or None
    if not author_name and not hal_id:
        return {"error": "Il faut fournir 'hal_id' ou 'author_name'", "query_url": None}
    if start_date and end_date and start_date > end_date:
        return {"error": f"start_date ({start_date}) doit être <= end_date ({end_date})", "query_url": None}

    result = await _search_author_publications(
        author_name=author_name,
        hal_id=hal_id,
        start_date=start_date,
        end_date=end_date,
        rows=rows,
    )
    if "error" in result:
        return result

    with_abstract = sum(1 for p in result["publications"] if p["abstract"])

    return {
        "num_found": result["num_found"],
        "total_returned": result["total_returned"],
        "has_more": result["has_more"],
        "with_abstract": with_abstract,
        "without_abstract": result["total_returned"] - with_abstract,
        "publications": result["publications"],
        "verification_url": result["verification_url"],
        "query_url": result["query_url"],
    }
