# HAL.Science MCP Server  

Le serveur de HAL-MCP fournit un ensemble d’outils permettant d’interroger l’API de l’archive ouverte **[HAL](https://hal.science/)**.

Ces outils s’appuient sur les [différentes endpoints de l'API HAL](https://api.archives-ouvertes.fr/docs/ref) afin d’accéder aux métadonnées des dépôts disponibles dans HAL.

À travers l’API de recherche (`search`), le MCP permet d’interroger les informations bibliographiques des publications scientifiques, notamment : le titre ; le résumé ; les auteurs ; les dates de publication ; le type de document et les identifiants associés (DOI, URI, etc.).

Le serveur consulte également d'autres référentiels HAL :`author` : référentiel des auteurs ; `structure` : référentiel des structures de recherche et `anrproject` : référentiel des projets ANR. 

---
# Connecter votre agent au serveur HAL MCP

Le serveur **HAL MCP** est actuellement disponible sur l’environnement de préproduction pour la phase de test :

- 🔗 service production : https://api.archives-ouvertes.fr/mcp
- 🔗 service preprod : https://api-preprod.archives-ouvertes.fr/mcp
---
# Outils disponibles

Nous avons développé une série de 9 outils permettant d’interroger les métadonnées HAL selon trois niveaux d’analyse :

## 1. Niveau auteur : recherche et analyse des profils scientifiques

Ces outils permettent d’explorer les informations relatives aux auteurs :

- `search_authors` : recherche d’auteurs dans HAL ;
- `search_author_publications` : consultation de leurs publications ;
- `get_author_affiliations` : identification de leurs affiliations. 

---

## 2. Niveau structure : analyse des activités de publication d'une struture

Ces outils permettent d’analyser les structures de recherche référencées dans HAL :

- `search_structures` : recherche des laboratoires, universités et institutions ;
- `search_structure_publications` : publications les plus récentes d'une ou plusieurs structures ;
- `get_publication_statistics_by_structure` : statistiques de production scientifique ;
- `count_anr_publications` : analyse des publications financées par l’ANR et mesure du niveau d’accès ouvert (*open access*) ;
- `search_lab_keyword_statistics` : identification des thématiques émergentes via les mots-clés des publications.

---

## 3. Niveau thématique : recherche de références sur un sujet

- `search_publications_by_topic` : recherche de publications portant sur un sujet ou une question de recherche, pour constituer une liste de références.

---

## 4. Recherche générique

- `search_documents` : accès direct (restreint) à l'API `/search` de HAL, pour les demandes qu'aucun outil spécialisé ne couvre ; l'agent compose lui-même la requête Solr.

---
# Promptothèque

Pour obtenir des réponses fiables, il est recommandé de formuler les questions en lien avec les fonctionnalités couvertes par les outils disponibles. 
Vous trouverez ci-dessous une série d'exemples de requêtes pouvant être utilisées directement ou adaptées selon vos besoins.

## Recherche d'auteurs

- Recherche l'auteur **Yutong Fei** dans HAL.
- Donne-moi l'identifiant HAL de **Yutong Fei**.
- Quelles sont les publications récentes de **Yutong Fei** ?
- Donne les publications de **Yutong Fei** entre 2022 et 2024.
- À quel laboratoire est affilié **Yutong Fei** ?
- Dans quelles structures de recherche **Yutong Fei** a-t-il travaillé ?

## Recherche de structures

- Quel est l'identifiant HAL de **l'Université Claude Bernard Lyon 1** ?
- Recherche l'identifiant HAL de **CCSD**.
- Recherche la structure **CREATIS**.
- Quelles sont les publications les plus récentes des **URFIST** ?
- Quelles sont les dernières publications de **CREATIS** ?

## Statistiques de publications

- Donne les statistiques de publication (nombre de publications, répartition par type de document) de **l'Université Claude Bernard Lyon 1** entre 2018 et 2023.
- Combien de publications a produites **CREATIS** entre 2020 et 2024 ?
- Quelle est l'évolution du nombre de publications de **LIRIS** entre 2019 et 2024 ?

## Publications financées par l'ANR

- Combien de publications financées par des projets ANR en accès ouvert possède **l'Université Claude Bernard Lyon 1** en 2025 ?
- Combien de publications financées par l'ANR sont affiliées à **CREATIS** entre 2020 et 2024 ?

## Analyse des thématiques de recherche

- Quels sont les principaux domaines de recherche de **l'Université Claude Bernard Lyon 1** en 2021 ?
- Quels sont les mots-clés les plus fréquents des publications de **CREATIS** en 2023 ?
- Quelles sont les thématiques émergentes de **LIRIS** en 2024 ?

## Recherche de références sur un sujet

- Quelles sont les **pratiques informationnelles des chercheurs** ? Donne-moi une liste de références.
- Trouve des articles et des thèses récents sur **la science ouverte en SHS** depuis 2020.
- Quels travaux en sciences de l'information portent sur **l'intelligence artificielle en éducation** ?

## Recherche générique

- Liste les **thèses en accès ouvert** produites en **2023** sur le **changement climatique**.
- Quelles publications HAL citent le projet **ANR-19-CE23-0001** ?
- Retrouve le document HAL qui a le DOI **10.1016/j.jtbi.2009.10.014**.
- Cherche les articles de la revue **Nature** dont un auteur a l'idHal **marie-curie**, avec les champs `abstract_s` et `keyword_s`.
---

# Vérification des résultats

Chaque outil renvoie des liens cliquables vers l'API HAL (`verification_url` ou `verification_urls`) qui listent les publications, auteurs ou structures derrière les chiffres retournés. Dans chaque lien, `numFound` en tête de la réponse est le nombre exact à comparer avec celui de l'outil ; pour les publications, les 100 plus récentes sont listées (titre, lien HAL, date, type).

| Outil | Liens fournis |
|---|---|
| `search_authors`, `search_structures` | un lien vers les résultats du référentiel |
| `search_author_publications` | un lien vers les publications de l'auteur, avec les mêmes filtres de dates |
| `get_author_affiliations` | un lien vers toutes les publications de l'auteur, et un par structure (publications où l'auteur y est rattaché) |
| `get_publication_statistics_by_structure` | toute la période, par année, par type de document |
| `count_anr_publications` | total, accès ouvert, hors accès ouvert |
| `search_lab_keyword_statistics` | toutes les publications de l'année, et un par mot-clé (30 premiers au plus) |
| `search_publications_by_topic` | un lien vers tous les résultats, dans le même ordre que l'outil |
| `search_structure_publications` | un lien vers toutes les publications, et un par structure |
| `search_documents` | un lien reproduisant la requête (`q`, `fq`, `sort`) |

# Description détaillée des outils

* `search_authors` : Recherche des auteurs dans le référentiel d’auteurs HAL à partir de leur prénom, nom ou d’une partie du nom.
Retourne les formes auteur correspondantes avec leur identifiant HAL (`hal_id`) et leur statut de validation.

| Paramètre | Type | Description |
|---|---|---|
| `query` | obligatoire | Prénom, nom ou fragment du nom de l’auteur à rechercher |
| `rows` | optionnel (défaut : 10, max : 100) | Nombre maximal d’auteurs retournés |

* `search_author_publications` : Recherche les publications d’un auteur dans HAL, les plus récentes d’abord, éventuellement sur une période donnée.
Retourne le nombre total de publications trouvées et les métadonnées des publications : titre ; résumé ; date de production ; type de document ; DOI lorsqu’il est disponible ; auteurs.

| Paramètre | Type | Description |
|---|---|---|
| `hal_id` | optionnel* | Identifiant HAL de l’auteur (recommandé : recherche exacte, sans homonymes) |
| `author_name` | optionnel* | Nom complet de l’auteur, tel qu’il apparaît dans les notices |
| `start_date` | optionnel | Date de début incluse (YYYY-MM-DD) |
| `end_date` | optionnel | Date de fin incluse (YYYY-MM-DD) |
| `rows` | optionnel (défaut : 50, max : 200) | Nombre maximal de publications retournées |

\* au moins un des deux ; `hal_id` est prioritaire si les deux sont fournis.

* `get_author_affiliations` : Recherche les affiliations d’un auteur enregistré dans HAL en analysant les structures associées à ses publications les plus récentes.
Retourne les structures classées selon leur fréquence d’apparition, avec la première et la dernière année où chacune apparaît.

| Paramètre | Type | Description |
|---|---|---|
| `author_name` | obligatoire | Nom de l’auteur |
| `rows` | optionnel (défaut : 100, max : 500) | Nombre maximal de publications analysées par auteur |

* `search_structures` : Recherche des structures de recherche référencées dans HAL (laboratoires, universités, institutions, etc.) à partir de leur nom ou de leur acronyme.
Retourne les structures correspondantes avec : leur identifiant HAL (`id`) ; leur type ; leurs tutelles (`parent_ids`, `parent_names`) ; leur statut de validation.

| Paramètre | Type | Description                      |
|---|---|----------------------------------|
| `structure_name` | obligatoire | Nom ou acronyme de la structure  |
| `rows` | optionnel (défaut : 50, max : 200) | Nombre maximal de structures retournées |

* `search_structure_publications` : Liste les publications les plus récentes d'une ou plusieurs structures de recherche, fusionnées et triées par date.
Retourne pour chaque publication : titre, auteurs, date, type, revue/conférence/ouvrage, lien HAL, lien DOI s'il existe, et la ou les structures concernées ; pour chaque structure : nom, sigle, tutelles, statut et nombre de publications.

| Paramètre | Type | Description |
|---|---|---|
| `struct_ids` | obligatoire | Identifiants HAL des structures (1 à 20), obtenus via `search_structures` |
| `start_date` / `end_date` | optionnel | Bornes incluses sur la date de production (YYYY-MM-DD) |
| `doc_types` | optionnel (défaut : tous) | Types de document (ex. `ART`, `COMM`) |
| `rows` | optionnel (défaut : 10, max : 50) | Nombre de publications retournées |

* `get_publication_statistics_by_structure` : Compte les publications d’une structure de recherche enregistrée dans HAL sur une période donnée.
Retourne le nombre de publications par année de production et par type de document. Le comptage est fait par HAL (facettes) : il est exact et exhaustif.

| Paramètre | Type | Description |
|---|---|---|
| `struct_id` | obligatoire | Identifiant HAL de la structure |
| `start_year` | obligatoire | Année de début |
| `end_year` | obligatoire | Année de fin |

* `count_anr_publications` : Compte les publications financées par des projets ANR, pour une structure de recherche et une période données.
Retourne : le nombre de publications financées par l’ANR ; dont en accès ouvert / hors accès ouvert ; la part en accès ouvert.

| Paramètre     | Type | Description                           |
|---------------|---|---------------------------------------|
| `struct_id`   | optionnel | Identifiant HAL de la structure (toutes structures si absent) |
| `start_date`  | optionnel | Date de début incluse (YYYY-MM-DD, date de production) |
| `end_date`    | optionnel | Date de fin incluse (YYYY-MM-DD) |

* `search_lab_keyword_statistics` : Analyse les thématiques émergentes d’une structure de recherche enregistrée dans HAL à partir de la distribution des mots-clés associés aux publications.
Retourne : le nombre total de publications pour une année donnée ; une agrégation des mots-clés classés selon leur fréquence d’apparition.

| Paramètre | Type | Description |
|---|---|---|
| `struct_id` | obligatoire | Identifiant HAL de la structure |
| `year` | obligatoire | Année de production analysée |
| `limit` | optionnel (défaut : 30, max : 200) | Nombre maximal de mots-clés retournés |

* `search_publications_by_topic` : Recherche des publications HAL portant sur un sujet ou une question de recherche, classées par pertinence ou par date.
Retourne une liste de références (titre, auteurs, année, type, revue/conférence/ouvrage, DOI, mots-clés, résumé tronqué, lien HAL) et la répartition de tous les résultats par discipline, type de document et année.
La recherche est lexicale : l'agent construit la requête en combinant synonymes et traduction anglaise (ex. `("pratiques informationnelles" OR "information practices") AND (chercheurs OR researchers)`).

| Paramètre | Type | Description |
|---|---|---|
| `query` | obligatoire | Requête (syntaxe Solr : expressions entre guillemets, AND / OR / NOT) |
| `start_year` / `end_year` | optionnel | Bornes incluses sur l'année de production |
| `doc_types` | optionnel (défaut : ART, COMM, THESE, OUV, COUV) | Types de document ; liste vide = tous les types |
| `domain` | optionnel | Code de discipline HAL, sous-domaines inclus (ex. `shs.info`) |
| `sort` | optionnel (défaut : `relevance`) | `relevance` ou `date` |
| `rows` | optionnel (défaut : 20, max : 50) | Nombre de références retournées |

* `search_documents` : Recherche générique dans les documents HAL (API `/search`, moteur Solr). L'agent compose lui-même la requête (`q`, `fq`, `sort`) et choisit les champs retournés (`fl`) ; la docstring de l'outil lui décrit la syntaxe Solr et une liste restreinte des champs HAL les plus utiles — un utilisateur averti peut lui indiquer d'autres champs.
Retourne le nombre total exact de documents (`num_found`) et les documents bruts tels que renvoyés par HAL. Accès volontairement partiel : pas de facettes, pas de pagination (`start`/`cursorMark`), sortie JSON forcée ; les paramètres locaux Solr (`{!...}`) sont refusés.

| Paramètre | Type | Description |
|---|---|---|
| `q` | optionnel (défaut : `*:*`) | Requête Solr principale |
| `fq` | optionnel (max : 20) | Liste de filtres Solr, combinés par ET |
| `sort` | optionnel (défaut : pertinence) | Clauses `<champ> asc\|desc` séparées par des virgules |
| `rows` | optionnel (défaut : 20, max : 100) | Nombre de documents retournés |
| `fl` | optionnel (défaut : `docid`, `halId_s`, `uri_s`, `label_s`, `title_s`, `authFullName_s`, `producedDateY_i`, `docType_s`, `doiId_s`) | Champs retournés |
