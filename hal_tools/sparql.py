from core.mcp import mcp
from hal_api.api_sparql import sparql as _sparql

# Modèle de données commun aux deux outils SPARQL (sparql, build_network).
SPARQL_DATA_MODEL = """
    MODÈLE DE DONNÉES HAL (préfixes hal, dcterms, dc, foaf, ore, skos, org, rdf, rdfs ajoutés
    automatiquement s'ils ne sont pas déclarés) :
      ?doc dcterms:creator ?aut          ?aut = « une personne sur un document » (hal:Author)
      ?aut hal:person ?personne          forme auteur (foaf:Person, foaf:name ?nom)
      ?personne ore:isAggregatedBy ?id   idHAL : <https://data.archives-ouvertes.fr/author/<idhal>>
      ?aut hal:structure ?s              affiliation déclarée SUR CE document
      ?s org:unitOf* ?tutelle            remonte aux tutelles (labo → université, CNRS…)
      ?s skos:prefLabel ?nom ; skos:altLabel ?sigle ; org:classification ?type
         ?type : <https://data.archives-ouvertes.fr/vocabulary/StructureType{Laboratory,
         Institution,Regroupinstitution,Researchteam,Department...}>
         structure : <https://data.archives-ouvertes.fr/structure/<structId>> (= structId_i Solr)
      ?doc dcterms:title ; dcterms:abstract ; dcterms:issued ?date ; dcterms:type ?doctype
         ?date a des types variés (année, année-mois, date) : filtrer sur l'année avec
         FILTER(SUBSTR(STR(?date), 1, 4) >= "2020")
         ?doctype : <https://data.archives-ouvertes.fr/doctype/{Article,ConferencePaper,Thesis...}>
      ?doc dc:subject ?motcle            mots-clés : dc:subject (PAS dcterms:subject), littéraux
                                         avec étiquette de langue : "science ouverte"@fr
      ?doc dcterms:isVersionOf ?depot    regroupe les versions v1, v2… d'un même dépôt :
         OPTIONAL { ?doc dcterms:isVersionOf ?o } BIND(COALESCE(?o, ?doc) AS ?depot)
      document : <https://data.archives-ouvertes.fr/document/<halId>>

    PIÈGES CONNUS :
      - Recherche plein texte `bif:contains` : ne renvoie plus rien (constaté en oct.-nov. 2026).
        Chercher les mots-clés exacts avec VALUES, en listant les variantes de casse et de langue :
        VALUES ?t { "open science"@en "Open science"@en "science ouverte"@fr "Science ouverte"@fr }
        Pour trouver un nom : FILTER(CONTAINS(LCASE(STR(?nom)), "schöpfel")), lent sur de gros
        ensembles ; préférer les outils Solr (search_authors, search_structures) pour obtenir
        l'identifiant, puis l'IRI correspondante.
      - Auteur·es sans notice dans le référentiel HAL : nœud hal:Author vide (ni nom, ni
        hal:person, ni hal:structure). Environ 40 % des signatures sur certains sujets : les
        résultats sur les auteur·es et les structures sont INCOMPLETS, le dire à l'utilisateur.
      - Formes auteur sans idHAL : une même personne peut apparaître plusieurs fois.
      - Le serveur plafonne toute réponse à 10 000 lignes.
"""


SPARQL_DOC = (
    """
    sparql - Requête SPARQL libre sur le point d'accès SPARQL de HAL
    (https://sparql.archives-ouvertes.fr/sparql), qui expose HAL sous forme de graphe RDF.

    UTILISER CET OUTIL pour les questions qui portent sur des RELATIONS que Solr ne sait pas
    parcourir : chaînes d'affiliation (laboratoire → tutelles), formes auteur regroupées sous un
    idHAL, co-auteur·es d'une personne, structures co-présentes sur des documents...
    Pour une recherche de publications par sujet, préférer `search` ou
    `search_publications_by_topic` (Solr : recherche lexicale, plus complète et plus rapide).
    Pour dessiner un réseau (co-autorat, co-affiliation, co-occurrence de mots-clés), utiliser
    `build_network`.

    REQUÊTE (`query`) : SELECT ou ASK uniquement (lecture seule). Refusés : mises à jour
    (INSERT, DELETE, LOAD...), CONSTRUCT, DESCRIBE, SERVICE (requêtes fédérées), DEFINE et toute
    fonction Virtuoso autre que bif:contains. LIMIT au plus 1000 (100 ajouté s'il est absent),
    pas d'OFFSET : affiner la requête plutôt que paginer. Agréger côté SPARQL (COUNT, GROUP BY)
    plutôt que de rapatrier des milliers de lignes.
    """ + SPARQL_DATA_MODEL + """
    EXEMPLES :
      Formes auteur et nombre de signatures d'un idHAL :
        SELECT ?forme ?nom (COUNT(DISTINCT ?aut) AS ?signatures) WHERE {
          ?forme ore:isAggregatedBy <https://data.archives-ouvertes.fr/author/joachim-schopfel> ;
                 foaf:name ?nom .
          ?aut hal:person ?forme .
        } GROUP BY ?forme ?nom
      Tutelles d'un laboratoire (structId 39707) :
        SELECT DISTINCT ?tutelle ?nom ?type WHERE {
          <https://data.archives-ouvertes.fr/structure/39707> org:unitOf+ ?tutelle .
          ?tutelle skos:prefLabel ?nom ; org:classification ?type .
        }

    Returns:
        vars, rows (lignes {variable: valeur}, textes longs tronqués à 1000 caractères),
        total_returned, limit_reached (true : il existe probablement d'autres résultats) ;
        boolean pour ASK ;
        sparql_query : requête réellement envoyée (préfixes compris) ;
        verification_url : lien qui rejoue la requête et affiche un tableau HTML ;
        sparql_queries : bloc Markdown prêt à afficher.
        En cas d'erreur : {"error", "query_url"}, avec le message de Virtuoso ; corriger la
        requête et relancer.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - Terminer la réponse par une section « Requêtes SPARQL utilisées » qui recopie TEL QUEL
        le champ `sparql_queries` de chaque appel retenu.
      - Ne citer que des documents, personnes ou structures présents dans `rows`.
    """
)


async def sparql(query: str):
    return await _sparql(query)


sparql.__doc__ = SPARQL_DOC
mcp.tool()(sparql)
