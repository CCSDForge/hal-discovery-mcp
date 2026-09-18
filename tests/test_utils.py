from utils import (
    aggregate_by_year_and_type,
    aggregate_publications_by_year_and_doctype,
    format_keyword_report,
)


def test_aggregate_by_year_and_type_counts_per_year_and_type():
    publications = [
        {"year": 2020, "type": "ART"},
        {"year": 2020, "type": "ART"},
        {"year": 2020, "type": "COMM"},
        {"year": 2021, "type": "ART"},
    ]

    stats = aggregate_by_year_and_type(publications)

    assert stats[2020]["ART"] == 2
    assert stats[2020]["COMM"] == 1
    assert stats[2021]["ART"] == 1


def test_aggregate_by_year_and_type_skips_publications_without_year():
    publications = [{"year": None, "type": "ART"}, {"type": "ART"}]

    stats = aggregate_by_year_and_type(publications)

    assert stats == {}


def test_aggregate_by_year_and_type_defaults_missing_type_to_unknown():
    stats = aggregate_by_year_and_type([{"year": 2020, "type": None}])

    assert stats[2020]["UNKNOWN"] == 1


def test_aggregate_publications_by_year_and_doctype_counts_and_returns_plain_dicts():
    publications = [
        {"publication_year": 2019, "doc_type": "ART"},
        {"publication_year": 2019, "doc_type": "ART"},
        {"publication_year": 2019, "doc_type": None},
    ]

    stats = aggregate_publications_by_year_and_doctype(publications)

    assert stats == {2019: {"ART": 2, "UNKNOWN": 1}}
    assert isinstance(stats[2019], dict)


def test_aggregate_publications_by_year_and_doctype_skips_missing_year():
    stats = aggregate_publications_by_year_and_doctype([{"doc_type": "ART"}])

    assert stats == {}


def test_format_keyword_report_includes_log_lines_and_top_keywords_only():
    keywords = {"ia": 42, "biologie": 30, "chimie": 5}

    report = format_keyword_report(["ligne 1", "ligne 2"], keywords, top_n=2)
    lines = report.splitlines()

    assert lines[0] == "ligne 1"
    assert lines[1] == "ligne 2"
    assert "Top 2 mots-clés :" in report
    assert "ia : 42" in report
    assert "biologie : 30" in report
    assert "chimie : 5" not in report
