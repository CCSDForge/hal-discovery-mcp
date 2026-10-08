from typing import Literal

from core.mcp import mcp
from hal_api.api_search import search as _search


@mcp.tool()
async def search(
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
):
    """
    search - Recherche générale dans HAL, comme la barre de recherche de l'interface : exécute
    une requête Solr composée librement et renvoie les documents trouvés, avec l'URL exacte de la
    requête. L'outil ne fait aucun calcul (classement, comptage) : il cherche et renvoie.

    UTILISER CET OUTIL lorsqu'aucun outil spécialisé ne couvre la question, par exemple :
      - "Quel est l'état de l'art sur les pratiques informationnelles liées aux LLM entre 2022 et
         2026 ?"
      - "Quelles thèses récentes portent sur la science ouverte ?"
    Préférer les outils spécialisés quand ils conviennent (search_authors, search_structures,
    search_publications_by_topic, get_structure_topics, search_projects...) : ils gèrent déjà la
    désambiguïsation, la mise en forme et les classements (auteurs, laboratoires...).

    POINTS D'ENTRÉE (`endpoint`) :
      - "search" : les dépôts (publications). Par défaut.
      - "ref/author", "ref/structure", "ref/anrproject", "ref/europeanproject", "ref/journal",
        "ref/domain" : référentiels (identifiants, formes de nom, sigles...). Leurs champs
        diffèrent de ceux de "search" : commencer par fl=* et rows=1 pour les découvrir.

    PARAMÈTRES (`params`, dictionnaire Solr ; liste de chaînes pour un paramètre répété) :
      q, fq, fl, sort, rows (0 à 100, défaut 10), q.op, df. fl=* n'est accepté qu'avec rows ≤ 5,
      pour découvrir les champs. Pas de pagination : affiner q / fq plutôt que de parcourir des
      pages de résultats.
      wt est imposé (json). Tout autre paramètre est refusé, en particulier start, cursorMark,
      facet.*, group.* et stats.* (trop coûteux pour HAL).
      Sont aussi refusés : les paramètres locaux {!...} (dans q, fq...), les fonctions dans `sort`
      (seulement « champ asc|desc ») et les transformateurs [..] dans `fl` (seulement des champs).

    CHAMPS UTILES DE "search" (suffixe = type : _s chaîne exacte, _t texte analysé,
    _i entier, _tdate date, _fs « partie_FacetSep_partie ») :
      Texte : title_t, abstract_t, keyword_t, text (titre+résumé+mots-clés, champ par défaut).
      Document : docid, halId_s, uri_s, docType_s (ART, COMM, THESE, OUV, COUV, HDR, REPORT,
        POSTER...), language_s, doiId_s, journalTitle_s, conferenceTitle_s, bookTitle_s, keyword_s.
      Dates : producedDateY_i (année de production, à privilégier), producedDate_tdate,
        submittedDate_tdate.
      Auteurs : authFullName_s, authIdHal_s (idHAL, identifiant stable), authStructId_i.
      Structures : structId_i, structAcronym_s, structName_s, labStructId_i, instStructId_i,
        labStructAcronym_s.
      Discipline : domain_s ("0.shs", "1.shs.info"...), primaryDomain_s, fr_domainAllCodeLabel_fs.
      Financements : anrProjectReference_s, europeanProjectAcronym_s.
      Liste complète : https://api.archives-ouvertes.fr/docs/search/?schema=fields

    MÉTHODE (une question = en général plusieurs appels) :
      1. Interpréter la question : concepts, période, types de documents, informations attendues.
      2. Requête thématique : comme pour search_publications_by_topic, synonymes et traduction
         anglaise reliés par OR, concepts reliés par AND, expressions entre guillemets. Mettre les
         contraintes non thématiques (période, type, domaine) dans `fq`, pas dans `q`.
      3. Sonder : rows=0 donne num_found. Trop de résultats ou de bruit → ajouter un concept,
         filtrer par domain_s ; zéro → élargir. Ex. : « recherche d'information » ramène le
         domaine « information retrieval » (informatique) plutôt que les pratiques des usagers.
      4. Récupérer les publications (rows 20 à 50, tri par pertinence, fl avec titre, auteurs,
         année, venue, résumé) et lire titres et résumés pour écarter le hors sujet.
      5. Si besoin, requêtes complémentaires (formulation anglaise seule, publications d'un auteur
         repéré : fq=authIdHal_s:"<idhal>").
      Exemple « LLM et pratiques informationnelles, 2022-2026 » :
        {"q": "(\"large language model\" OR \"large language models\" OR LLM OR ChatGPT
               OR \"IA générative\" OR \"generative AI\")
               AND (\"information practices\" OR \"information behavior\" OR \"information seeking\"
               OR \"pratiques informationnelles\" OR \"information literacy\")",
         "fq": ["producedDateY_i:[2022 TO 2026]", "docType_s:(ART OR COMM OR THESE OR OUV OR COUV)"],
         "fl": "halId_s,uri_s,title_s,authFullName_s,producedDateY_i,docType_s,journalTitle_s,abstract_s",
         "rows": 30}

    Returns:
        num_found / total_returned: nombre total de documents correspondants et nombre renvoyé.
        docs: documents bruts (champs de `fl`), textes longs tronqués à 1000 caractères.
        solr_params: paramètres réellement envoyés.
        readable_url: requête lisible, non encodée, pour la montrer à l'utilisateur.
        query_url: URL exacte et cliquable envoyée à HAL.
        verification_url ("search"): lien listant les mêmes publications par pertinence, avec
            titres et liens HAL.
        solr_queries: bloc Markdown prêt à afficher (forme lisible, lien cliquable, numFound).
        En cas d'erreur : {"error", "query_url"} ; corriger la requête et relancer.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - Restituer une synthèse ET, en fin de réponse, une section « Requêtes Solr utilisées » où
        est recopié TEL QUEL le champ `solr_queries` de chaque appel retenu pour la réponse (sans
        le reformuler ni le raccourcir), pour que la recherche soit vérifiable et reproductible.
      - Ne citer que des documents présents dans `docs`, avec leur `uri_s`. Ne jamais inventer
        ni compléter une référence à partir de connaissances générales.
      - Un état de l'art tiré de HAL se limite aux dépôts HAL et à la recherche lexicale : le
        signaler, et ne pas présenter la synthèse comme exhaustive.
    """
    return await _search(endpoint, params)
