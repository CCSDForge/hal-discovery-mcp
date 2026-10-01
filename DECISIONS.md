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
