from datetime import date

import hal_tools.count_anr_publications as tool_module
from hal_tools.count_anr_publications import count_anr_publications


async def test_count_anr_publications_delegates_to_logic(monkeypatch):
    captured = {}

    async def fake_logic(**kwargs):
        captured.update(kwargs)
        return {"total_anr_publications": 1}

    monkeypatch.setattr(tool_module, "count_anr_publications_logic", fake_logic)

    result = await count_anr_publications(struct_id=194495, start_date=date(2020, 1, 1))

    assert result == {"total_anr_publications": 1}
    assert captured == {"struct_id": 194495, "start_date": date(2020, 1, 1), "end_date": None}