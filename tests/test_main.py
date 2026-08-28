import json

from pacs_query import run


def test_run_creates_report(
    monkeypatch,
    tmp_path,
    default_options,
):
    search_results = [
        {
            "PatientID": "TEST",
            "StudyInstanceUID": "1.2.3",
            "SeriesInstanceUID": "1.2.3.1",
        }
    ]

    monkeypatch.setattr(
        "pacs_query.cfind",
        lambda options, directive: search_results,
    )

    monkeypatch.setattr(
        "pacs_query.pfdcm.sanitize",
        lambda directive: (directive, None),
    )

    monkeypatch.setattr(
        "pacs_query.pfdcm.autocomplete_directive",
        lambda directive, response: (
            response,
            1,
        ),
    )

    default_options.outputdir = str(tmp_path)

    run(
        default_options,
        tmp_path,
        tmp_path,
    )

    report = tmp_path / "search_results.json"

    assert report.exists()

    data = json.loads(report.read_text())

    assert data == search_results