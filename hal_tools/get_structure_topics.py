from datetime import date
from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_get_structure_topics import get_structure_topics as _get_structure_topics

DEFAULT_YEARS = 3
MAX_YEARS = 30


@mcp.tool()
async def get_structure_topics(
    struct_ids: Annotated[list[int], Field(min_length=1, max_length=20)],
    start_year: int | None = None,
    end_year: int | None = None,
    compare: bool = True,
    doc_types: list[str] | None = None,
    top: Annotated[int, Field(ge=1, le=50)] = 20,
):
    """
    get_structure_topics - Décrit les thématiques de recherche d'une ou de plusieurs structures HAL
    (laboratoires, universités...) : mots-clés et disciplines dominants sur une période et,
    par comparaison avec la période précédente, thématiques émergentes ou en recul.

    UTILISER CET OUTIL lorsque l'utilisateur demande, par exemple :
      - "Sur quoi travaille le laboratoire ELICO ?"
      - "Quels sont les principaux travaux de CREATIS ?"
      - "Quelles sont les thématiques émergentes du LIRIS ?"

    NE PAS utiliser cet outil pour lister les publications d'une structure
    (`search_structure_publications`) ni pour trouver les laboratoires qui travaillent sur un
    sujet donné (`search_publications_by_topic`).

    Workflow :
      1. Appeler d'abord `search_structures` pour obtenir les identifiants (`id`).
      2. Passer dans `struct_ids` tous les identifiants de la même entité (ex. fiche VALID et
         ancienne fiche OLD du même laboratoire), en un seul appel. Attention aux homonymes : un
         même sigle peut désigner des structures sans rapport (ex. « ELICO » : un laboratoire
         lyonnais de sciences de l'information et un ancien laboratoire de chimie marine). Vérifier
         le nom complet et les tutelles avant de regrouper.

    Parameters:
        struct_ids: Identifiants HAL des structures (1 à 20). Un établissement inclut ses
            laboratoires.
        start_year / end_year: Période analysée (années de production, incluses). Par défaut : les
            3 dernières années, année en cours comprise (elle est incomplète : le signaler).
        compare: Comparer avec la période précédente de même durée (par défaut : True), pour
            repérer les thématiques émergentes ou en recul.
        doc_types: Codes des types de document (ex. ["ART", "COMM", "THESE"]). Par défaut : tous.
        top: Nombre de mots-clés retournés (1 à 50, par défaut : 20).

    Returns:
        structures: id, name, acronym, validation_status de chaque structure demandée.
        period / reference_period: start_year, end_year, num_publications (total exact),
            analyzed_docs (au plus 2000, les plus récentes), exhaustive, docs_with_keywords
            (publications ayant des mots-clés), verification_url.
        main_keywords: [{keyword, count, verification_url}] mots-clés les plus fréquents de la
            période (en minuscules ; variantes de casse regroupées, français et anglais NON
            regroupés).
        main_domains: [{code, label, count}] 10 disciplines HAL les plus fréquentes.
        emerging_keywords (si `compare`): [{keyword, recent_count, reference_count, recent_share,
            reference_share, status, verification_url}] mots-clés « nouveau » (absents de la période
            de référence) ou « en hausse » (part au moins doublée), du plus au moins progressant.
            Les parts (%) sont rapportées aux publications ayant des mots-clés.
        declining_keywords (si `compare`): même forme, status « en recul » (part au moins divisée
            par deux).
        comparison_error: si la période de référence n'a pas pu être analysée.
        readable_url: requête Solr de la période analysée (première page).
        Les liens `verification_url` d'un mot-clé listent les publications dont un mot-clé
        CONTIENT l'expression : leur `numFound` peut dépasser `count`.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - Synthétiser les travaux principaux à partir de `main_domains` et `main_keywords`, en
        regroupant les variantes françaises et anglaises d'un même thème (ex. « open science » et
        « science ouverte »).
      - Les mots-clés sont ceux saisis par les déposants : beaucoup de publications n'en ont pas
        (comparer `docs_with_keywords` à `analyzed_docs`). Le signaler si la proportion est faible.
      - Une thématique « émergente » est un mot-clé dont la part augmente dans les dépôts HAL de la
        structure ; avec peu de publications, rester prudent. Un seul auteur très productif peut
        suffire à faire émerger un mot-clé : vérifier avec le lien avant d'en faire une tendance
        du laboratoire. Ne jamais présenter ces tendances
        comme une analyse exhaustive de l'activité du laboratoire.
      - Si `exhaustive` vaut False, préciser que seules les publications les plus récentes de la
        période ont été analysées.
      - Donner le lien `verification_url` de la période et, pour les thématiques citées, leur lien.
    """
    current_year = date.today().year
    end_year = end_year if end_year is not None else current_year
    start_year = start_year if start_year is not None else end_year - DEFAULT_YEARS + 1
    if start_year > end_year:
        return {"error": f"start_year ({start_year}) doit être <= end_year ({end_year})", "query_url": None}
    if end_year - start_year + 1 > MAX_YEARS:
        return {"error": f"La période ne peut pas dépasser {MAX_YEARS} ans", "query_url": None}

    return await _get_structure_topics(
        struct_ids=struct_ids,
        start_year=start_year,
        end_year=end_year,
        compare=compare,
        doc_types=doc_types,
        top=top,
    )
