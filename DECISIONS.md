# DECISIONS.md

Historique des choix structurants du projet (architecture, technologies, conventions,
abandon de pistes). Une entrée par décision : date, décision, contexte/raison. Quand une
décision remet en cause une entrée précédente, la nouvelle entrée doit citer l'ancienne
et expliquer pourquoi elle ne tient plus, plutôt que de la remplacer silencieusement.

---

## 2026-09-18 — Ajout des tests unitaires (`tests/`) : pytest + pytest-asyncio

**Décision** : `pytest` + `pytest-asyncio` (mode `auto`) plutôt que `unittest`, pour les tests
unitaires de `hal_api/*` et `hal_tools/*`. Dépendances de test isolées dans
`requirements-dev.txt` (inclut `requirements.txt`).

**Contexte** : tout le code métier est asynchrone (`aiohttp`/`httpx`) ; `pytest-asyncio` évite le
boilerplate de `unittest.IsolatedAsyncioTestCase` et permet d'écrire les tests comme de simples
fonctions `async def test_...`, sans marker explicite grâce à `asyncio_mode = auto`
(`pytest.ini`). Les appels réseau sont simulés via des fakes maison dans `tests/conftest.py`
(fixtures `fake_aiohttp`/`fake_httpx`), pour éviter une dépendance de mock HTTP supplémentaire
(`aioresponses`/`respx`).

**Contrainte** : `make test` ne peut pas faire `pip install`
directement dans le Python système sur un hôte Debian/Ubuntu récent (erreur PEP 668
"externally-managed-environment"). La cible `test` du `Makefile` crée donc un venv local
(`venv/`, déjà exclu par `.gitignore`) et y installe `requirements-dev.txt` avant de lancer
`pytest`, plutôt que de supposer un environnement Python déjà préparé.

---

## 2026-09-18 — Migration `mcp<2` → `mcp>=2` (`FastMCP` → `MCPServer`), branche `mcp2.0`

---

## 2026-09-28 — Client HTTP unique (`hal_api/client.py`, httpx) ; abandon d'`aiohttp`

**Décision** : tous les appels à l'API HAL passent par `hal_api.client.hal_get`, basé sur
`httpx` uniquement. `aiohttp` est retiré de `requirements.txt`. Remet en cause l'entrée
« Ajout des tests unitaires » du 2026-09-18 sur un point : la fixture `fake_aiohttp` n'a
plus lieu d'être, seule `fake_httpx` subsiste dans `tests/conftest.py`.

**Contexte** : les modules `hal_api/*` utilisaient deux bibliothèques HTTP, avec des timeouts
différents (10 s, 15 s, 60 s ou aucun) et une gestion d'erreur propre à chacun (dict
`error`, `raise_for_status`, `ValueError`, `KeyError` possibles). `hal_get` impose un seul
contrat : `{"data", "query_url"}` en cas de succès, `{"error", "query_url"}` sinon, sans
jamais lever d'exception réseau. Il centralise aussi l'échappement des valeurs saisies
(`escape_phrase`) pour qu'un `"` ne casse pas une requête Solr.

---

## 2026-09-28 — Comptages par facettes Solr plutôt que par rapatriement des documents

**Décision** : `get_publication_statistics_by_structure` utilise `facet.pivot=producedDateY_i,docType_s`
avec `rows=0`, comme `search_lab_keyword_statistics` le faisait déjà pour les mots-clés.

**Contexte** : l'ancienne version rapatriait jusqu'à 10 000 documents pour les compter en
Python ; au-delà, les statistiques étaient tronquées (`has_more`). Les facettes donnent des
chiffres exacts en une requête légère, quel que soit le volume.

---

## 2026-09-28 — Date de production (`producedDate*`) pour tous les filtres temporels

**Décision** : tous les outils filtrent sur la date de production (`producedDateY_i` ou
`producedDate_tdate`). `count_anr_publications` utilisait `publicationDate_tdate`.

**Contexte** : avec deux champs différents, les chiffres d'un même laboratoire sur une même
période ne concordaient pas d'un outil à l'autre.

---

## 2026-09-28 — Recherche thématique lexicale, requête construite par l'agent

**Décision** : `search_publications_by_topic` transmet à Solr une requête écrite par l'agent
(synonymes et traduction anglaise reliés par OR, concepts reliés par AND), plutôt que de
tenter une recherche sémantique ou de reformuler côté serveur.

**Contexte** : HAL n'offre qu'une recherche lexicale. Sur « pratiques informationnelles des
chercheurs », la requête brute ou en anglais seul est bruitée ; une requête combinant
synonymes FR/EN et restreinte aux types scientifiques donne les meilleurs résultats. Le LLM
sait produire ces variantes : la docstring lui décrit la méthode. Les codes `doc_types` et
`domain`, insérés tels quels dans les filtres, sont validés par expression régulière.

**Conséquence pour tous les outils** : sur une syntaxe Solr invalide, HAL répond 200 avec
`{"error": ...}`. `hal_get` traite désormais ce cas comme une erreur, au lieu de laisser
croire à « 0 résultat ».

---

## 2026-09-28 — Outil dédié `search_structure_publications` plutôt qu'un ajout à `search_structures`

**Décision** : les publications d'une structure sont servies par un outil séparé, sur le modèle
`search_authors` / `search_author_publications`, et `search_structures` reste un outil
d'identification.

**Contexte** : `search_structures` est appelé avant presque tous les autres outils pour obtenir un
identifiant ; y ajouter 10 publications par structure (jusqu'à 50 structures) alourdirait chaque
appel. Le nouvel outil accepte plusieurs identifiants, car une même entité peut être répartie
sur plusieurs structures (ex. 7 URFIST, qui portent toutes le même nom et se distinguent par
leur sigle). Les structures `OLD` sont incluses : le tri par date les relègue naturellement.

---

## 2026-10-02 — Outil générique `hal_solr_search`, sans facettes

**Décision** : un seul outil transmet à l'API Solr de HAL des requêtes composées par l'agent et
renvoie la réponse avec la requête exacte. Les outils spécialisés sont conservés.
Aucune facette, aucun `group` ni `stats` : sur demande (option `aggregate`), les classements
(auteurs, laboratoires, revues) sont calculés en Python sur au plus 500 documents, les plus
pertinents d'abord ; les comptes exacts (option `count_by`) reposent sur une requête `rows=0`
par tranche. Ces calculs sont des fonctions internes (`hal_api/utils.py`), pas des outils MCP :
un premier essai en trois outils (`hal_solr_aggregate`, `hal_solr_count`) multipliait les
points d'entrée, ce que l'outil générique devait justement éviter. Pour ces
outils, cela va à l'inverse de l'entrée « Comptages par facettes Solr » du 2026-09-28, qui
reste valable pour les outils spécialisés.

**Contexte** : tous les outils reposent sur `search` ou `ref/*` ; chaque question non prévue
(ex. « auteurs qui publient le plus sur un sujet, sur une période ») demandait un nouvel outil.
L'agent sait écrire du Solr si la docstring lui décrit les champs et la méthode. Les facettes sur
des champs à forte cardinalité (auteurs, structures) coûtent cher à HAL ; laissées à la main
d'un agent, elles seraient appelées sans retenue. Récupérer quelques centaines de documents
avec un `fl` réduit, ou compter avec `rows=0`, reste léger.

**Contrepartie** : au-delà de `max_docs`, un classement ne porte que sur les publications les
plus pertinentes (`exhaustive: false`), ce que l'agent doit signaler. Pour un « qui compte sur ce
sujet », c'est souvent préférable : les derniers résultats d'une recherche lexicale sont les
plus bruités.

**Garde-fous** : liste blanche de paramètres (`wt` imposé ; `facet.*`, `group.*`, `stats.*`,
`qt`, `stream.*`… refusés), liste fermée de points d'entrée, bornes sur `rows`, `start`,
`aggregate_max_docs` et le nombre de tranches, au plus 4 requêtes de comptage simultanées, textes longs
tronqués dans la réponse.

**Transparence** : chaque réponse de `hal_solr_search` contient `solr_queries`, un bloc Markdown
prêt à afficher (requête lisible, lien cliquable, numFound de chaque requête envoyée). Recopier
un bloc tout fait est plus fiable que de demander à l'agent de reconstituer les requêtes à partir
des champs épars. Les `instructions` du serveur MCP (`core/mcp.py`), transmises au client à la
connexion, demandent de le recopier en fin de réponse.

---

## 2026-10-03 — Outils recentrés sur quatre parcours, plus aucune facette

**Décision** : les outils suivent les questions des utilisateurs, en quatre parcours, avec
`hal_solr_search` en recours :
- **sujet** : `search_publications_by_topic`, qui donne aussi les laboratoires, auteurs et
  disciplines dominants ;
- **auteur** : `search_authors`, `search_author_publications` (avec un profil thématique),
  `get_author_affiliations` ;
- **structure** : `search_structures`, `search_structure_publications`, `get_structure_topics`
  (nouveau : thématiques principales, émergentes et en recul) ;
- **projets** : `search_projects` et `get_project_publications` (nouveaux, ANR et européens).

`get_publication_statistics_by_structure`, `search_lab_keyword_statistics` et
`count_anr_publications` sont supprimés : des comptages par année, type ou accès ouvert ne
répondent pas aux questions des chercheurs, et `hal_solr_search` (`count_by`) les couvre si besoin.
`get_structure_topics` remplace `search_lab_keyword_statistics`, qui ne donnait les mots-clés que
d'une année, sans comparaison possible, donc sans repérer ce qui émerge.

**Aucune facette** : remet en cause l'entrée « Comptages par facettes Solr » du 2026-09-28 et la
réserve de l'entrée « Outil générique » du 2026-10-02, qui conservait les facettes des outils
spécialisés. Les `facet.query` par structure deviennent une requête `rows=0` par structure
(comptes exacts) ; les répartitions et classements sont calculés en Python
(`hal_api.utils.collect_values`) sur les publications les plus pertinentes (sujet, projets) ou
les plus récentes (auteur, structure, projet), avec un `fl` réduit au strict nécessaire.
Chaque classement indique `analyzed_docs` et `exhaustive`. Le coût pour HAL n'a pas été mesuré :
à comparer (`QTime`) avec l'équipe qui exploite le Solr.

**Ordre d'analyse** : sans requête thématique (`q=*:*`), tous les scores sont égaux et le tri par
pertinence revenait à analyser les publications les plus anciennement déposées. `aggregate` trie
désormais par date décroissante dans ce cas (`order` dans la réponse).

**Garde-fous de `hal_solr_search`** : la liste blanche portait sur les noms de paramètres, pas sur
leur contenu. HAL accepte les paramètres locaux (`{!join}`, `{!frange}`...) et les transformateurs
de documents (`[explain]`, `[subquery]`), vérifié le 2026-10-03 : ils sont refusés, `fl` est
limité à des noms de champs et `sort` à `champ asc|desc`.

**Limites connues** : les mots-clés sont ceux des déposants (beaucoup de publications n'en ont
pas ; français et anglais ne sont pas regroupés, l'agent s'en charge) ; un auteur très productif
peut suffire à faire « émerger » un mot-clé ; les programmes ANR structurants (IdEx, LabEx, EUR...)
dominent les classements de projets par publications, d'où l'indicateur `structuring_program`.
