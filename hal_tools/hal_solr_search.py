from typing import Annotated, Literal

from pydantic import Field

from core.mcp import mcp
from hal_api.api_hal_solr_search import hal_solr_search as _hal_solr_search
from hal_api.utils import MAX_AGGREGATE_DOCS, MAX_TOP


@mcp.tool()
async def hal_solr_search(
    params: dict[str, str | int | list[str]],
    endpoint: Literal[
        "search",
        "ref/author",
        "ref/structure",
        "ref/anrproject",
        "ref/europeanproject",
        "ref/journal",
        "ref/domain",
    ] = "search",
    aggregate: list[str] | None = None,
    aggregate_max_docs: Annotated[int, Field(ge=1, le=MAX_AGGREGATE_DOCS)] = 300,
    aggregate_top: Annotated[int, Field(ge=1, le=MAX_TOP)] = 15,
    count_by: dict[str, str] | None = None,
):
    """
    hal_solr_search - Exécute une requête Solr composée librement sur l'API HAL et renvoie les
    documents, ainsi que, sur demande, des classements (`aggregate`) et des comptes par tranche
    (`count_by`) calculés sans facette. Renvoie toujours l'URL exacte de la requête.

    UTILISER CET OUTIL lorsqu'aucun outil spécialisé ne couvre la question, par exemple :
      - "Quel est l'état de l'art sur les pratiques informationnelles liées aux LLM entre 2022 et
         2026, et quels en sont les auteurs importants ?"
      - "Combien de thèses en informatique par an depuis 2015 ?"
      - "Quelles revues publient le plus sur la science ouverte ?"
    Préférer les outils spécialisés quand ils conviennent (search_authors, search_structures,
    search_publications_by_topic, get_structure_topics, search_projects...) : ils gèrent déjà la
    désambiguïsation et la mise en forme.

    POINTS D'ENTRÉE (`endpoint`) :
      - "search" : les dépôts (publications). Par défaut.
      - "ref/author", "ref/structure", "ref/anrproject", "ref/europeanproject", "ref/journal",
        "ref/domain" : référentiels (identifiants, formes de nom, sigles...). Leurs champs
        diffèrent de ceux de "search" : commencer par fl=* et rows=1 pour les découvrir.

    PARAMÈTRES (`params`, dictionnaire Solr ; liste de chaînes pour un paramètre répété) :
      q, fq, fl, sort, rows (0 à 100, défaut 10), start (≤ 1000 ; au-delà, paginer avec cursorMark
      et un tri se terminant par docid, ex. sort="producedDate_tdate desc,docid asc", cursorMark="*"),
      q.op, df. fl=* n'est accepté qu'avec rows ≤ 5, pour découvrir les champs.
      wt est imposé (json). Tout autre paramètre est refusé, en particulier facet.*, group.* et
      stats.* (trop coûteux pour HAL) : pour classer ou compter, utiliser les options ci-dessous.
      Sont aussi refusés : les paramètres locaux {!...} (dans q, fq...), les fonctions dans `sort`
      (seulement « champ asc|desc ») et les transformateurs [..] dans `fl` (seulement des champs).

    OPTIONS DE CALCUL (point d'entrée "search" uniquement ; portent sur les mêmes q / fq que
    `params`, indépendamment de rows / fl / sort) :
      aggregate: 1 à 8 champs dont classer les valeurs les plus fréquentes, ex.
          ["authFullNameIdHal_fs", "labStructIdName_fs", "journalTitle_s", "fr_domainAllCodeLabel_fs"].
          Calculé sur TOUTES les publications correspondantes jusqu'à 5000 résultats. Au-delà,
          seulement sur `aggregate_max_docs` publications (1 à 500, défaut 300) : les plus
          pertinentes, ou les plus récentes si q vaut *:* (`order` le précise), avec un `warning`
          (des auteurs importants peuvent manquer : affiner q / fq pour passer sous 5000).
          Chaque valeur compte une fois par document ; les formes de nom d'un même idHAL sont
          regroupées ; `aggregate_top` valeurs par champ (1 à 50, défaut 15).
          Pour « qui / quels laboratoires / quelles revues… ».
      count_by: au plus 30 tranches, libellé -> filtre fq ajouté, ex.
          {"2022": "producedDateY_i:2022", "2023": "producedDateY_i:2023"} ou
          {"articles": "docType_s:ART", "thèses": "docType_s:THESE"}. Comptes EXACTS (une requête
          rows=0 par tranche). Pour une évolution dans le temps ou une répartition connue.
      Mettre rows=0 si seuls les calculs sont utiles.

    CHAMPS UTILES DE "search" (suffixe = type : _s chaîne exacte, _t texte analysé,
    _i entier, _tdate date, _fs « partie_FacetSep_partie ») :
      Texte : title_t, abstract_t, keyword_t, text (titre+résumé+mots-clés, champ par défaut).
      Document : docid, halId_s, uri_s, docType_s (ART, COMM, THESE, OUV, COUV, HDR, REPORT,
        POSTER...), language_s, doiId_s, journalTitle_s, conferenceTitle_s, bookTitle_s, keyword_s.
      Dates : producedDateY_i (année de production, à privilégier), producedDate_tdate,
        submittedDate_tdate.
      Auteurs : authFullName_s, authIdHal_s (idHAL, identifiant stable), authFullNameIdHal_fs
        (nom + idHAL, idéal pour classer), authStructId_i.
      Structures : structId_i, structAcronym_s, structName_s, labStructId_i, instStructId_i,
        labStructAcronym_s, labStructIdName_fs (identifiant + nom du laboratoire, idéal pour classer).
      Discipline : domain_s ("0.shs", "1.shs.info"...), primaryDomain_s, fr_domainAllCodeLabel_fs.
      Financements : anrProjectReference_s, europeanProjectAcronym_s.
      Liste complète : https://api.archives-ouvertes.fr/docs/search/?schema=fields

    MÉTHODE (une question = en général plusieurs appels) :
      1. Interpréter la question : concepts, période, types de documents, informations attendues
         (références, auteurs, laboratoires, tendances...).
      2. Requête thématique : comme pour search_publications_by_topic, synonymes et traduction
         anglaise reliés par OR, concepts reliés par AND, expressions entre guillemets. Mettre les
         contraintes non thématiques (période, type, domaine) dans `fq`, pas dans `q`.
      3. Sonder : rows=0 donne num_found ; aggregate=["fr_domainAllCodeLabel_fs"] montre si la
         requête est bruitée. Ex. : « recherche
         d'information » ramène le domaine « information retrieval » (informatique) plutôt que
         les pratiques des usagers. Trop de bruit → ajouter un concept, filtrer par domain_s ;
         zéro → élargir.
      4. Récupérer les publications (rows 20 à 50, tri par pertinence, fl avec titre, auteurs,
         année, venue, résumé) et lire titres et résumés pour écarter le hors sujet.
      5. Classer auteurs, laboratoires, revues : `aggregate`. Évolution par année ou répartition
         par type : `count_by` (comptes exacts). Les deux peuvent accompagner l'étape 4.
      6. Si besoin, requêtes complémentaires (formulation anglaise seule, publications d'un auteur
         repéré : fq=authIdHal_s:"<idhal>").
      Exemple « LLM et pratiques informationnelles, 2022-2026 » :
        {"q": "(\"large language model\" OR \"large language models\" OR LLM OR ChatGPT
               OR \"IA générative\" OR \"generative AI\")
               AND (\"information practices\" OR \"information behavior\" OR \"information seeking\"
               OR \"pratiques informationnelles\" OR \"information literacy\")",
         "fq": ["producedDateY_i:[2022 TO 2026]", "docType_s:(ART OR COMM OR THESE OR OUV OR COUV)"],
         "fl": "halId_s,uri_s,title_s,authFullName_s,producedDateY_i,docType_s,journalTitle_s,abstract_s",
         "rows": 30}
        avec aggregate=["authFullNameIdHal_fs", "labStructIdName_fs"] et
        count_by={"2022": "producedDateY_i:2022", ..., "2026": "producedDateY_i:2026"}.

    Returns:
        num_found / total_returned: nombre total de documents correspondants et nombre renvoyé.
        docs: documents bruts (champs de `fl`), textes longs tronqués à 1000 caractères.
        next_cursor_mark: si cursorMark a été fourni (page suivante).
        aggregations (si `aggregate`): analyzed_docs, num_found, exhaustive, warning (si
            partiel), order ("relevance" ou "most_recent" : quelles publications ont été
            analysées), fields ({champ: {distinct_values, top: [{value, count}]}}), pages,
            readable_url. Si `exhaustive` est False, ne pas présenter le classement comme
            représentatif : affiner la requête et relancer, ou à défaut le dire explicitement. Pour les champs _fs, parties séparées par " | "
            (ex. "Yolande Maury | yolande-maury").
        counts (si `count_by`): {libellé: {fq, num_found, query_url}} (ou {fq, error, query_url}).
            Les tranches peuvent se recouper : leur somme n'est pas forcément num_found.
        solr_params: paramètres réellement envoyés.
        readable_url: requête lisible, non encodée, pour la montrer à l'utilisateur.
        query_url: URL exacte et cliquable envoyée à HAL.
        verification_url ("search"): lien listant les mêmes publications par pertinence, avec
            titres et liens HAL.
        solr_queries: bloc Markdown prêt à afficher, listant toutes les requêtes envoyées à HAL
            pour cet appel (forme lisible, lien cliquable, numFound).
        En cas d'erreur : {"error", "query_url"} ; corriger la requête et relancer.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - Restituer une synthèse ET, en fin de réponse, une section « Requêtes Solr utilisées » où
        est recopié TEL QUEL le champ `solr_queries` de chaque appel retenu pour la réponse (sans
        le reformuler ni le raccourcir), pour que la recherche soit vérifiable et reproductible.
      - Ne citer que des documents présents dans `docs`, avec leur `uri_s`. Ne jamais inventer
        ni compléter une référence à partir de connaissances générales.
      - « Auteurs importants » : les classements mesurent le nombre de dépôts HAL correspondant à
        la requête, pas l'influence (HAL ne fournit pas de citations). Le dire explicitement.
      - Un état de l'art tiré de HAL se limite aux dépôts HAL et à la recherche lexicale : le
        signaler, et ne pas présenter la synthèse comme exhaustive.
    """
    return await _hal_solr_search(
        endpoint,
        params,
        aggregate=aggregate,
        aggregate_max_docs=aggregate_max_docs,
        aggregate_top=aggregate_top,
        count_by=count_by,
    )

