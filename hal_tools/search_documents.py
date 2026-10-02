from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_documents import MAX_FQ, MAX_ROWS, search_documents as _search_documents


@mcp.tool()
async def search_documents(
    q: str = "*:*",
    fq: Annotated[list[str] | None, Field(max_length=MAX_FQ)] = None,
    sort: str | None = None,
    rows: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 20,
    fl: list[str] | None = None,
):
    """
    search_documents - Recherche générique dans les documents HAL (API /search, moteur Solr), avec une
    requête Solr composée librement par l'agent. Renvoie les documents bruts, avec les champs demandés.

    UTILISER CET OUTIL lorsqu'aucun outil spécialisé ne couvre la demande, par exemple :
      - "Liste les thèses en accès ouvert soutenues en 2023 dans le laboratoire X"
      - "Les publications HAL qui ont le DOI 10.xxxx/yyyy"
      - "Les articles financés par le projet ANR ANR-19-CE23-0001"
      - une combinaison de critères (auteur + structure + période + type + revue...)
      - lorsque l'utilisateur fournit lui-même des noms de champs HAL ou une requête Solr

    NE PAS utiliser cet outil quand un outil dédié existe :
      - identifier un auteur / obtenir son idHal : `search_authors`
      - identifier une structure / obtenir son struct_id : `search_structures`
        (les identifiants numériques à utiliser dans `fq` viennent de ces outils, jamais d'une supposition)
      - publications d'un auteur : `search_author_publications` ; d'une structure : `search_structure_publications`
      - recherche thématique avec répartition par discipline/type/année : `search_publications_by_topic`
      - statistiques ou comptages agrégés (par année, par type, par mot-clé) : `get_publication_statistics_by_structure`,
        `search_lab_keyword_statistics`, `count_anr_publications`. Cet outil ne fournit PAS de facettes :
        ne jamais compter « à la main » sur une page de 100 documents pour produire une statistique.

    LIMITES : pas de facettes, pas de pagination (une seule page, `rows` <= 100, les premiers selon `sort`),
    sortie JSON. Pour un simple comptage, `rows=1` suffit : `num_found` donne le total exact.

    SYNTAXE (Solr / Lucene) :
      - Champ:valeur : title_t:climat ; expression exacte : title_t:"changement climatique"
      - Opérateurs AND / OR / NOT EN MAJUSCULES, parenthèses : (climat OR climate) AND docType_s:ART
      - Intervalles bornes incluses : producedDateY_i:[2020 TO 2024], producedDate_tdate:[2023-01-01T00:00:00Z TO *]
      - Joker : authLastName_s:Dup* ; tout : *:* ; champ renseigné : doiId_s:*
      - Échapper les caractères spéciaux d'une valeur hors guillemets : doiId_s:10.1000\\/xyz ou
        doiId_s:"10.1000/xyz"
      - `q` sert à la recherche (avec score de pertinence) ; `fq` pour les filtres stricts (pas de score,
        mis en cache) : préférer `fq` pour type, période, structure, auteur identifié.
      - Les paramètres locaux Solr `{!...}` sont refusés.

    RECHERCHE THÉMATIQUE (sur un sujet) :
      - Chercher dans title_t, abstract_t et keyword_t plutôt que dans `text` (ou une requête sans champ,
        qui utilise `text`) : `text` couvre TOUTES les métadonnées (affiliations, noms de revue ou de
        conférence, financements...) et ramène beaucoup de bruit. Forme recommandée, avec T la liste des
        termes : title_t:(T) OR abstract_t:(T) OR keyword_t:(T)
      - Éviter les sigles et termes courts ambigus, qui correspondent aussi à des noms d'institutions ou à
        d'autres disciplines : ex. MPI (aussi « Max Planck Institute »), GPU, IA, HPC, CNN... Leur préférer des
        expressions entre guillemets ("parallel computing", "message passing interface"), ou les combiner
        par AND avec un terme du domaine.
      - Contrôler la pertinence sur un échantillon (titre, résumé, mots-clés) : un terme peut être employé
        dans un autre sens (ex. « parallélisme » entre deux théorèmes). Si le bruit domine, resserrer la
        requête et relancer plutôt que présenter les résultats tels quels.

    CONVENTION DE SUFFIXES des champs HAL :
      _t texte analysé (insensible à la casse, recherche par mots) ; _s chaîne exacte (sensible à la casse,
      valeur complète) ; _i entier ; _tdate date ISO ; _bool booléen (true/false) ; `text` = tous les champs texte.

    CHAMPS DE RECHERCHE LES PLUS UTILES (liste volontairement restreinte) :
      Contenu :
        text                     recherche plein texte toutes métadonnées (champ par défaut)
        title_t / abstract_t / keyword_t   titre, résumé, mots-clés (texte analysé)
      Auteurs :
        authFullName_t           nom complet, recherche par mots (ex. authFullName_t:"marie curie")
        authFullName_s           nom complet exact, tel que saisi (ex. "Marie Curie")
        authLastName_s           nom de famille exact
        authIdHal_s              idHal textuel (ex. "marie-curie"), le plus fiable une fois l'auteur identifié
        authIdHal_i              idHal numérique
        authORCIDIdExt_s         ORCID (ex. "0000-0002-1825-0097")
      Structures :
        structId_i               identifiant de structure (toute structure affiliée, tous niveaux)
        labStructId_i / instStructId_i     identifiant de laboratoire / d'institution
        structAcronym_s / labStructAcronym_s   sigle exact (ex. "LIRMM")
        structName_t             nom de structure (texte analysé)
      Type, dates, discipline, langue :
        docType_s                ART article, COMM communication, THESE, HDR, OUV ouvrage, COUV chapitre,
                                 REPORT rapport, POSTER, PROCEEDINGS, MEM mémoire, UNDEFINED prépublication /
                                 document de travail, SOFTWARE, OTHER...
        producedDateY_i / producedDate_tdate   année / date de production (date de référence des autres outils)
        publicationDateY_i       année de publication
        submittedDate_tdate      date de dépôt dans HAL
        domain_s                 discipline HAL préfixée par la profondeur : "0.shs", "1.shs.info"
        language_s               code langue (fr, en...)
      Publication, identifiants, financement, accès :
        journalTitle_t / journalIssn_s     revue (titre analysé / ISSN exact)
        conferenceTitle_t        conférence
        doiId_s                  DOI (sans préfixe https://doi.org/)
        halId_s                  identifiant HAL (ex. "hal-01234567")
        anrProjectReference_s    référence de projet ANR (ex. "ANR-19-CE23-0001")
        europeanProjectAcronym_s acronyme de projet européen
        collCode_s               code de collection HAL
        openAccess_bool          true si le texte intégral est en accès ouvert
        submitType_s             file (avec texte intégral), notice (métadonnées seules), annex
      HAL comporte beaucoup d'autres champs : si l'utilisateur en indique un, l'utiliser tel quel.
      Ne jamais inventer un nom de champ hors de cette liste et de ceux donnés par l'utilisateur.

    Parameters:
        q: Requête Solr principale (par défaut "*:*", tous les documents).
        fq: Liste de filtres Solr, combinés par ET (au plus 20), ex. ["docType_s:ART", "producedDateY_i:[2020 TO *]"].
        sort: Tri, une ou plusieurs clauses "<champ> asc|desc" séparées par des virgules. Par défaut :
            pertinence (score desc). Champs de tri usuels : producedDate_tdate, submittedDate_tdate,
            publicationDate_tdate, title_sort, score, docid. Trier sur un champ monovalué uniquement.
        rows: Nombre de documents retournés (1 à 100, par défaut 20).
        fl: Liste des champs à retourner. Par défaut : docid, halId_s, uri_s, label_s (référence
            bibliographique complète), title_s, authFullName_s, producedDateY_i, docType_s, doiId_s.
            Champs utiles en plus : abstract_s, keyword_s, journalTitle_s, conferenceTitle_s, structName_s,
            labStructAcronym_s, authIdHal_s, openAccess_bool, language_s, citationRef_s.
            Les champs `_t` sont indexés mais non stockés : les demander dans fl ne renvoie rien,
            utiliser l'équivalent `_s`.

    Returns:
        num_found: nombre total exact de documents correspondant à la requête.
        total_returned: nombre de documents retournés (<= rows).
        has_more: True si d'autres documents existent au-delà de ceux retournés.
        fields: liste des champs effectivement demandés (fl).
        docs: documents HAL tels que renvoyés par l'API, clés = noms de champs HAL. Un champ absent d'un
            document signifie qu'il n'est pas renseigné (ou que le nom de champ n'existe pas : HAL ignore
            silencieusement les champs inconnus dans fl et sort). Les champs multivalués sont des listes.
        verification_url: lien cliquable vers l'API HAL reproduisant la requête (q, fq, sort).
        query_url: URL exacte de la requête envoyée.
        En cas d'échec : {"error": ..., "query_url": ...} ; une syntaxe Solr invalide ou un nom de champ
        inconnu dans q/fq produit une erreur « L'API HAL a rejeté la requête ».

    RÈGLES ANTI-HALLUCINATION :
      - Ne rapporter que ce qui figure dans `docs` ; ne jamais compléter un champ absent à partir de
        connaissances générales, ni inventer un identifiant, un titre, un auteur ou une affiliation.
      - Ne jamais deviner un identifiant numérique (structId_i, authIdHal_i...) : l'obtenir via
        `search_structures` / `search_authors`, ou de l'utilisateur. En cas d'homonymes, ne pas en choisir
        un silencieusement.
      - Si `error` est présent : le signaler tel quel, corriger la requête si l'erreur est de syntaxe,
        sans inventer de résultat.
      - Si `num_found == 0` : le dire, et proposer d'élargir (champ _t plutôt que _s, moins de filtres,
        variantes orthographiques) plutôt que d'affirmer que rien n'existe.
      - Si `has_more` est True : préciser que la liste est partielle (seuls `total_returned` documents sur
        `num_found`) ; ne pas extrapoler de statistique depuis cet échantillon.
      - Indiquer la requête utilisée et le lien `verification_url`, recopié tel quel.
    """
    return await _search_documents(q=q, fq=fq, sort=sort, rows=rows, fl=fl)
