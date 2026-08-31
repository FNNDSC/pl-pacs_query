from pacs_query import cfind

def test_series_query_uses_study_instance_uid(
    monkeypatch,
    default_options,
    study_dataset,
    series_dataset,
):
    identifiers = []

    class FakeAssociation:
        is_established = True

        def send_c_find(self, identifier, model):
            identifiers.append(identifier)

            if len(identifiers) == 1:
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

    cfind(
        default_options,
        {
            "PatientID": "TEST",
            "StudyDate": "20251027",
        },
    )

    assert len(identifiers) == 2

    study_identifier = identifiers[0]
    series_identifier = identifiers[1]

    assert study_identifier.QueryRetrieveLevel == "STUDY"

    assert series_identifier.QueryRetrieveLevel == "SERIES"
    assert (
        series_identifier.StudyInstanceUID
        == study_dataset.StudyInstanceUID
    )

def test_cfind_queries_series_for_each_study(
    monkeypatch,
    default_options,
    study_dataset,
    study_dataset_2,
    series_dataset,
):
    queried_studies = []

    class FakeAssociation:
        is_established = True

        def send_c_find(self, identifier, model):
            if identifier.QueryRetrieveLevel == "STUDY":
                return [
                    (
                        type("Status", (), {"Status": 0xFF00})(),
                        study_dataset,
                    ),
                    (
                        type("Status", (), {"Status": 0xFF00})(),
                        study_dataset_2,
                    ),
                    (
                        type("Status", (), {"Status": 0x0000})(),
                        None,
                    ),
                ]

            queried_studies.append(
                identifier.StudyInstanceUID
            )

            return [
                (
                    type("Status", (), {"Status": 0x0000})(),
                    None,
                )
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

    assert result == []

    assert queried_studies == [
        study_dataset.StudyInstanceUID,
        study_dataset_2.StudyInstanceUID,
    ]