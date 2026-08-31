from pacs_query import cfind


def test_cfind_performs_two_stage_query(
    monkeypatch,
    default_options,
    study_dataset,
    series_dataset,
):
    calls = []

    class FakeAssociation:
        is_established = True

        def send_c_find(self, identifier, model):
            calls.append(identifier)

            if len(calls) == 1:
                # STUDY query response
                return [
                    (
                        type("Status", (), {"Status": 0xFF00})(),
                        study_dataset,
                    ),
                    (
                        type("Status", (), {"Status": 0x0000})(),
                        None,
                    ),
                ]

            # SERIES query response
            return [
                (
                    type("Status", (), {"Status": 0xFF00})(),
                    series_dataset,
                ),
                (
                    type("Status", (), {"Status": 0x0000})(),
                    None,
                ),
            ]

        def release(self):
            pass

    class FakeAE:
        def __init__(self, ae_title):
            pass

        def add_requested_context(self, model):
            pass

        def associate(self, ip, port, ae_title):
            return FakeAssociation()

    monkeypatch.setattr("pacs_query.AE", FakeAE)

    result = cfind(
        default_options,
        {
            "PatientID": "TEST",
            "StudyDate": "20251027",
        },
    )

    assert len(calls) == 2
    assert len(result) == 1

    assert result[0]["StudyInstanceUID"] == (
        study_dataset.StudyInstanceUID
    )

    assert result[0]["SeriesInstanceUID"] == (
        series_dataset.SeriesInstanceUID
    )