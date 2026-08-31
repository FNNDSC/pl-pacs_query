from pacs_query import cfind
from pydicom.dataset import Dataset

def test_cfind_returns_empty_on_association_failure(
    monkeypatch,
    default_options,
):
    class FakeAssociation:
        is_established = False

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
        },
    )

    assert result == []

def test_cfind_skips_study_without_uid(
    monkeypatch,
    default_options,
):
    study = Dataset()
    study.PatientID = "TEST"

    class FakeAssociation:
        is_established = True

        def send_c_find(self, identifier, model):
            return [
                (
                    type("Status", (), {"Status": 0xFF00})(),
                    study,
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
        },
    )

    assert result == []

