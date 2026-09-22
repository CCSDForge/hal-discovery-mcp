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
