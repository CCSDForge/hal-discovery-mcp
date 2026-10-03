import hal_tools.get_project_publications as publications_module
import hal_tools.search_projects as search_module
from hal_tools.get_project_publications import get_project_publications
from hal_tools.search_projects import search_projects


async def test_search_projects_rejects_empty_query_and_inverted_years():
    assert "error" in await search_projects(query="  ")
    assert "error" in await search_projects(query="llm", start_year=2025, end_year=2020)


async def test_search_projects_delegates(monkeypatch):
    captured = {}

    async def fake(query, **kwargs):
        captured.update(query=query, **kwargs)
        return {}

    monkeypatch.setattr(search_module, "_search_projects", fake)

    await search_projects(query=" llm ", kind="europe")

    assert captured == {"query": "llm", "kind": "europe", "start_year": None, "end_year": None, "rows": 10}


async def test_get_project_publications_requires_project(monkeypatch):
    async def fake(project, **kwargs):
        return {"project": project, **kwargs}

    monkeypatch.setattr(publications_module, "_get_project_publications", fake)

    assert "error" in await get_project_publications(project=" ")
    assert await get_project_publications(project=" GrAI ") == {"project": "GrAI", "kind": "both", "rows": 20}
