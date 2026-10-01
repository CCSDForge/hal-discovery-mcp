from typing import Annotated, Literal

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_publications_by_topic import (
    DEFAULT_DOC_TYPES,
    search_publications_by_topic as _search_publications_by_topic,
)


@mcp.tool()
async def search_publications_by_topic(
    query: str,
    start_year: int | None = None,
    end_year: int | None = None,
    doc_types: list[str] | None = None,
    domain: str | None = None,
    sort: Literal["relevance", "date"] = "relevance",
    rows: Annotated[int, Field(ge=1, le=50)] = 20,
):
    """
    search_publications_by_topic - Recherche dans HAL des publications portant sur un sujet ou une
    question de recherche, pour proposer une liste de références pertinentes.

    UTILISER CET OUTIL lorsque l'utilisateur cherche des travaux sur un thème, par exemple :
      - "Quelles sont les pratiques informationnelles des chercheurs ?"
      - "Trouve des références sur la science ouverte en SHS"
      - "Quels travaux portent sur l'intelligence artificielle en éducation depuis 2020 ?"

    NE PAS utiliser cet outil pour les publications d'un auteur précis (`search_author_publications`)
    ni pour la production d'une structure (`get_publication_statistics_by_structure`).

    CONSTRUCTION DE LA REQUÊTE (`query`, syntaxe Solr) :
      La recherche est lexicale (mots présents dans le titre, le résumé, les mots-clés...), pas
      sémantique : un article qui n'emploie pas les termes cherchés ne sortira pas. Pour de bons
      résultats :
        1. Identifier les concepts de la question (ex. : « pratiques informationnelles » + « chercheurs »).
        2. Pour chaque concept, lister synonymes et traduction anglaise, en expressions entre guillemets,
           reliés par OR.
        3. Relier les concepts par AND.
      Exemple pour « pratiques informationnelles des chercheurs » :
        ("pratiques informationnelles" OR "comportements informationnels" OR "usages de l'information"
         OR "information practices" OR "information behavior" OR "information seeking")
        AND (chercheur OR chercheurs OR researchers OR scientists OR doctorants)
      Opérateurs AND / OR / NOT en majuscules ; guillemets et parenthèses équilibrés.
      Si trop peu de résultats : élargir (plus de synonymes, retirer un concept). Si trop de bruit :
      ajouter un concept, filtrer par `domain` (voir `facets.by_domain`) ou par période.
      Ne pas hésiter à lancer plusieurs recherches (ex. formulation française puis anglaise).

    Parameters:
        query: Requête Solr (voir ci-dessus).
        start_year / end_year: Bornes incluses sur l'année de production (optionnelles).
        doc_types: Codes des types de document à inclure. Par défaut (None) : publications
            scientifiques ART (article), COMM (communication), THESE, OUV (ouvrage), COUV (chapitre).
            Autres codes possibles : HDR, REPORT, MEM (mémoire), POSTER, PROCEEDINGS, OTHER...
            Liste vide [] : tous les types.
        domain: Code de discipline HAL pour filtrer (sous-domaines inclus), ex. "shs" ou "shs.info".
            Utiliser un code renvoyé dans `facets.by_domain` plutôt que de le deviner.
        sort: "relevance" (par défaut, les plus pertinentes d'abord) ou "date" (les plus récentes d'abord).
        rows: Nombre de publications retournées (1 à 50, par défaut : 20).

    Returns:
        num_found / total_returned / has_more: nombre total de publications correspondantes, nombre
            retourné, et `True` si la liste n'est pas exhaustive.
        publications: pour chacune hal_id, url, title, authors (10 premiers), num_authors, year, type,
            venue (revue, conférence ou ouvrage), doi, keywords, abstract (tronqué), language.
        facets: répartition de TOUS les résultats (pas seulement ceux retournés) :
            by_domain ([{code, label, count}], 10 premières disciplines), by_doc_type, by_year.
        verification_url: lien cliquable vers l'API HAL listant les résultats dans le même ordre ;
            `numFound` en tête de la réponse est égal à `num_found`.
        query_url: URL exacte de la requête envoyée à l'API HAL.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - La pertinence est calculée sur les mots, pas sur la qualité ou l'influence (HAL ne fournit
        pas de nombre de citations). Lire titre, résumé et mots-clés, et écarter les publications
        hors sujet plutôt que de les présenter.
      - Ne citer que des références présentes dans `publications`, avec leur lien `url`. Ne jamais
        inventer ni compléter une référence à partir de connaissances générales.
      - Présenter les références sous forme de liste (auteurs, année, titre, venue, lien), en
        expliquant brièvement pourquoi chacune est pertinente.
      - Indiquer `num_found`, la requête utilisée et le lien `verification_url`, recopié tel quel.
      - Rappeler que la couverture se limite aux dépôts HAL : ce n'est pas une revue de
        littérature exhaustive.
    """
    if not query or not query.strip():
        return {"error": "Le paramètre 'query' est requis et ne peut pas être vide", "query_url": None}
    if start_year is not None and end_year is not None and start_year > end_year:
        return {"error": f"start_year ({start_year}) doit être <= end_year ({end_year})", "query_url": None}

    result = await _search_publications_by_topic(
        query=query.strip(),
        start_year=start_year,
        end_year=end_year,
        doc_types=DEFAULT_DOC_TYPES if doc_types is None else doc_types,
        domain=domain.strip() if domain else None,
        sort=sort,
        rows=rows,
    )
    if "error" in result:
        return result

    return {"query": query.strip(), **result}
