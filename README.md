# HAL Discovery MCP Server  

Le serveur de HAL-MCP fournit un ensemble d’outils permettant d’interroger l’API de l’archive ouverte **[HAL](https://hal.science/)**.

Ces outils s’appuient sur les [différentes endpoints de l'API HAL](https://api.archives-ouvertes.fr/docs/ref) afin d’accéder aux métadonnées des dépôts disponibles dans HAL.

À travers l’API de recherche (`search`), le MCP permet d’interroger les informations bibliographiques des publications scientifiques, notamment : le titre ; le résumé ; les auteurs ; les dates de publication ; le type de document et les identifiants associés (DOI, URI, etc.).

Le serveur consulte également d'autres référentiels HAL : `author` (auteurs), `structure` (structures de recherche), `anrproject` (projets ANR) et `europeanproject` (projets européens).

Aucun outil n'utilise de facette Solr, coûteuse pour HAL : les classements (laboratoires, auteurs, mots-clés, disciplines, projets) sont calculés par le serveur MCP à partir de requêtes légères (`hal_api/utils.py`).

---
# Connecter votre agent au serveur HAL MCP

Le serveur **HAL MCP** est actuellement disponible sur l’environnement de préproduction pour la phase de test :

- 🔗 service production : https://api.archives-ouvertes.fr/mcp
- 🔗 service preprod : https://api-preprod.archives-ouvertes.fr/mcp
---
# Outils disponibles

Nous avons développé une série de 10 outils, organisés selon quatre parcours, plus un outil de requête libre :

## 1. Sujet : publications et acteurs d'un thème

- `search_publications_by_topic` : publications portant sur un sujet ou une question de recherche, avec les laboratoires, auteurs et disciplines qui publient le plus sur ce sujet.

---

## 2. Auteur : qui est-ce, sur quoi travaille-t-il, où ?

- `search_authors` : recherche d'auteurs dans HAL (identifiant idHAL) ;
- `search_author_publications` : publications d'un auteur et profil thématique (disciplines, mots-clés, période d'activité) ;
- `get_author_affiliations` : laboratoires et établissements de rattachement au fil du temps.

---

## 3. Structure : identifiant, publications, thématiques

- `search_structures` : recherche des laboratoires, universités et institutions (identifiant HAL) ;
- `search_structure_publications` : publications les plus récentes d'une ou plusieurs structures ;
- `get_structure_topics` : travaux principaux (mots-clés, disciplines) et thématiques émergentes.

---

## 4. Projets ANR et européens

- `search_projects` : projets liés à un thème, par leur titre (référentiels) et par les publications qu'ils financent ;
- `get_project_publications` : publications d'un projet et leurs thématiques.

---

## 5. Requête libre : pour les questions que les autres outils ne couvrent pas

- `hal_solr_search` : quand aucun outil ne correspond à la question, LLM écrit lui-même la requête à envoyer à HAL. Il peut ainsi répondre à des questions plus variées.

Pour que la réponse reste vérifiable, la requête utilisée est toujours affichée, avec un lien qui permet de la relancer dans HAL.

---
# Promptothèque

Pour obtenir des réponses fiables, il est recommandé de formuler les questions en lien avec les fonctionnalités couvertes par les outils disponibles. 
Vous trouverez ci-dessous une série d'exemples de requêtes pouvant être utilisées directement ou adaptées selon vos besoins.

## Profil d'un auteur

- Recherche l'auteur **Prénom Nom** dans HAL. 
- Sur quoi travaille **Prénom Nom** ? Dans quel domaine ?
- Quelles sont les publications récentes de **Prénom Nom** ?
- Donne les publications de **Prénom Nom** entre 2022 et 2024.
- Quel est le laboratoire de rattachement de **Prénom Nom** ?
- Dans quelles structures de recherche a travaillé **Prénom Nom** ?

## Recherche de structures

- Quel est l'identifiant HAL de **l'Université Claude Bernard Lyon 1** ?
- Recherche l'identifiant HAL de **CCSD**.
- Recherche la structure **CREATIS**.
- Quelles sont les publications les plus récentes des **URFIST** ?

## Thématiques d'une structure

- Sur quoi travaille le laboratoire **ELICO** ?
- Quelles sont les thématiques émergentes du **LIRIS** depuis 2023 ?
- Quels sont les principaux domaines de recherche de **l'Université Claude Bernard Lyon 1** entre 2020 et 2022 ?

## Recherche de références sur un sujet

- Quelles sont les **pratiques informationnelles des chercheurs** ? Appui toi sur le serveur MCP de HAL.
- Trouve des articles et des thèses récents sur **la science ouverte en SHS** depuis 2020.
- Quels travaux en sciences de l'information portent sur **l'intelligence artificielle en éducation** ?
- Quels laboratoires publient le plus sur **les humanités numériques** ?

## Projets ANR et européens

- Quels projets ANR portent sur **l'intelligence artificielle en éducation** ?
- Quels projets européens financent des recherches sur **les grands modèles de langue** ?
- Quelles sont les publications et les thématiques du projet ANR **OPEN IT** ?
---

# Description détaillée des outils

* `search_authors` : Recherche des auteurs dans le référentiel d’auteurs HAL à partir de leur prénom, nom ou d’une partie du nom.
Retourne les formes auteur correspondantes avec leur identifiant HAL (`hal_id`) et leur statut de validation.

| Paramètre | Type | Description |
|---|---|---|
| `query` | obligatoire | Prénom, nom ou fragment du nom de l’auteur à rechercher |
| `rows` | optionnel (défaut : 10, max : 100) | Nombre maximal d’auteurs retournés |

* `search_author_publications` : Recherche les publications d’un auteur dans HAL, les plus récentes d’abord, éventuellement sur une période donnée.
Retourne le nombre total de publications trouvées et les métadonnées des publications : titre ; résumé ; date de production ; type de document ; DOI lorsqu’il est disponible ; auteurs.
Retourne aussi un profil thématique, calculé sur ses 500 publications les plus récentes au plus : disciplines et mots-clés les plus fréquents, première et dernière année, répartition par type.

| Paramètre | Type | Description |
|---|---|---|
| `hal_id` | optionnel* | Identifiant HAL de l’auteur (recommandé : recherche exacte, sans homonymes) |
| `author_name` | optionnel* | Nom complet de l’auteur, tel qu’il apparaît dans les notices |
| `start_date` | optionnel | Date de début incluse (YYYY-MM-DD) |
| `end_date` | optionnel | Date de fin incluse (YYYY-MM-DD) |
| `rows` | optionnel (défaut : 50, max : 200) | Nombre maximal de publications retournées |
| `include_profile` | optionnel (défaut : `true`) | Calculer le profil thématique |

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
Retourne pour chaque publication : titre, auteurs, date, type, revue/conférence/ouvrage, lien HAL, lien DOI s'il existe, et la ou les structures concernées ; pour chaque structure : nom, sigle, tutelles, statut et nombre exact de publications (une requête `rows=0` par structure).

| Paramètre | Type | Description |
|---|---|---|
| `struct_ids` | obligatoire | Identifiants HAL des structures (1 à 20), obtenus via `search_structures` |
| `start_date` / `end_date` | optionnel | Bornes incluses sur la date de production (YYYY-MM-DD) |
| `doc_types` | optionnel (défaut : tous) | Types de document (ex. `ART`, `COMM`) |
| `rows` | optionnel (défaut : 10, max : 50) | Nombre de publications retournées |

* `get_structure_topics` : Décrit les thématiques d'une ou plusieurs structures sur une période (par défaut les 3 dernières années) : mots-clés et disciplines les plus fréquents et, par comparaison avec la période précédente de même durée, mots-clés émergents (nouveaux ou dont la part a au moins doublé) ou en recul.
Les publications de chaque période (2 000 au plus, les plus récentes) sont parcourues avec seulement leurs mots-clés et disciplines ; les mots-clés sont regroupés sans tenir compte de la casse.

| Paramètre | Type | Description |
|---|---|---|
| `struct_ids` | obligatoire | Identifiants HAL des structures (1 à 20) |
| `start_year` / `end_year` | optionnel (défaut : les 3 dernières années) | Période analysée, 30 ans au plus |
| `compare` | optionnel (défaut : `true`) | Comparer avec la période précédente |
| `doc_types` | optionnel (défaut : tous) | Types de document |
| `top` | optionnel (défaut : 20, max : 50) | Nombre de mots-clés retournés |

* `search_publications_by_topic` : Recherche des publications HAL portant sur un sujet ou une question de recherche, classées par pertinence ou par date.
Retourne une liste de références (titre, auteurs, année, type, revue/conférence/ouvrage, DOI, mots-clés, résumé tronqué, lien HAL) et, calculés sur les 300 publications les plus pertinentes, les laboratoires, auteurs et disciplines les plus fréquents et la répartition par année et par type.
La recherche est lexicale : l'agent construit la requête en combinant synonymes et traduction anglaise (ex. `("pratiques informationnelles" OR "information practices") AND (chercheurs OR researchers)`).

| Paramètre | Type | Description |
|---|---|---|
| `query` | obligatoire | Requête (syntaxe Solr : expressions entre guillemets, AND / OR / NOT) |
| `start_year` / `end_year` | optionnel | Bornes incluses sur l'année de production |
| `doc_types` | optionnel (défaut : ART, COMM, THESE, OUV, COUV) | Types de document ; liste vide = tous les types |
| `domain` | optionnel | Code de discipline HAL, sous-domaines inclus (ex. `shs.info`) |
| `sort` | optionnel (défaut : `relevance`) | `relevance` ou `date` |
| `rows` | optionnel (défaut : 20, max : 50) | Nombre de références retournées |

* `search_projects` : Recherche les projets ANR et européens liés à un thème : d'une part les projets dont le titre, l'acronyme ou la référence correspondent (référentiels `anrproject` et `europeanproject`), d'autre part ceux qui financent le plus de publications sur ce thème (300 publications les plus pertinentes). Les programmes ANR structurants (IdEx, LabEx, EUR...) sont signalés.

| Paramètre | Type | Description |
|---|---|---|
| `query` | obligatoire | Thème (syntaxe Solr), acronyme ou référence |
| `kind` | optionnel (défaut : `both`) | `anr`, `europe` ou `both` |
| `start_year` / `end_year` | optionnel | Bornes sur l'année des publications financées |
| `rows` | optionnel (défaut : 10, max : 50) | Nombre de projets retournés par référentiel |

* `get_project_publications` : Liste les publications financées par un projet, les plus récentes d'abord, avec les mots-clés, disciplines et laboratoires les plus fréquents (500 publications au plus) et le ou les projets effectivement désignés.

| Paramètre | Type | Description |
|---|---|---|
| `project` | obligatoire | Identifiant HAL du projet, référence (ex. `ANR-19-CHIA-0003`) ou acronyme |
| `kind` | optionnel (défaut : `both`) | `anr`, `europe` ou `both` |
| `rows` | optionnel (défaut : 20, max : 50) | Nombre de publications retournées |

* `hal_solr_search` : Exécute une requête Solr composée par l'agent sur l'API HAL et renvoie les documents bruts, avec la requête exacte (`query_url`, cliquable) et sa forme lisible (`readable_url`).
Les paramètres sont contrôlés avant l'envoi : liste blanche (`q`, `fq`, `fl`, `sort`, `start`, `rows`, `cursorMark`, `q.op`, `df` ; facettes, regroupements et statistiques refusés), contenu contrôlé (paramètres locaux `{!...}` refusés, `fl` limité à des noms de champs, `sort` à `champ asc|desc`), `rows` ≤ 100, `start` ≤ 10 000 ; les textes longs sont tronqués dans la réponse.

| Paramètre | Type | Description |
|---|---|---|
| `params` | obligatoire | Dictionnaire de paramètres Solr (`q` requis ; liste de chaînes pour un paramètre répété, ex. `fq`) |
| `endpoint` | optionnel (défaut : `search`) | `search`, `ref/author`, `ref/structure`, `ref/anrproject`, `ref/europeanproject`, `ref/journal`, `ref/domain` |
| `aggregate` | optionnel (1 à 8 champs, `search` uniquement) | Champs dont classer les valeurs, ex. `authFullNameIdHal_fs`, `labStructIdName_fs`, `journalTitle_s` ; calculé sur les publications les plus pertinentes, ou les plus récentes si `q` vaut `*:*` (`exhaustive: false` si `num_found` dépasse `aggregate_max_docs`) |
| `aggregate_max_docs` | optionnel (défaut : 300, max : 500) | Nombre de publications analysées pour `aggregate` |
| `aggregate_top` | optionnel (défaut : 15, max : 50) | Nombre de valeurs retournées par champ |
| `count_by` | optionnel (max : 30 tranches, `search` uniquement) | Libellé → filtre ajouté, ex. `{"2024": "producedDateY_i:2024"}` ; une requête `rows=0` par tranche, au plus 4 en parallèle |

