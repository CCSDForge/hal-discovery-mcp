from datetime import date

import hal_tools.get_structure_topics as tool_module
from hal_tools.get_structure_topics import get_structure_topics


async def test_defaults_to_last_three_years(monkeypatch):
    captured = {}

    async def fake(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(tool_module, "_get_structure_topics", fake)

    await get_structure_topics(struct_ids=[70904])

    year = date.today().year
    assert (captured["start_year"], captured["end_year"]) == (year - 2, year)
    assert captured["compare"] is True


async def test_rejects_inverted_or_too_long_period(monkeypatch):
    async def fake(**kwargs):
        raise AssertionError("HAL ne doit pas être appelé")

    monkeypatch.setattr(tool_module, "_get_structure_topics", fake)

    assert "error" in await get_structure_topics(struct_ids=[1], start_year=2025, end_year=2020)
    assert "error" in await get_structure_topics(struct_ids=[1], start_year=1950, end_year=2025)
