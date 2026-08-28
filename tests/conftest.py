import json
from argparse import Namespace

import pytest
from pydicom.dataset import Dataset


class FakeStatus:
    def __init__(self, status):
        self.Status = status


@pytest.fixture
def default_options(tmp_path):
    return Namespace(
        src_aet="TEST_PACS",
        src_ip="127.0.0.1",
        src_port=104,
        dst_aet="TEST_CLIENT",
        PACSdirective=json.dumps(
            {
                "PatientID": "TEST",
                "StudyDate": "20251027",
            }
        ),
        reportName="search_results",
        query_model="study",
        outputdir=str(tmp_path),
    )


@pytest.fixture
def study_dataset():
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4.1"
    ds.PatientID = "TEST"
    ds.PatientName = "TEST"
    ds.StudyDate = "20251027"
    return ds


@pytest.fixture
def study_dataset_2():
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4.2"
    ds.PatientID = "TEST"
    ds.PatientName = "TEST"
    ds.StudyDate = "20251027"
    return ds


@pytest.fixture
def series_dataset():
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4.1"
    ds.SeriesInstanceUID = "1.2.3.4.1.1"
    ds.SeriesNumber = "1"
    ds.Modality = "MR"
    ds.SeriesDescription = "T1"
    ds.NumberOfSeriesRelatedInstances = 100
    return ds


@pytest.fixture
def series_dataset_2():
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4.1"
    ds.SeriesInstanceUID = "1.2.3.4.1.2"
    ds.SeriesNumber = "2"
    ds.Modality = "MR"
    ds.SeriesDescription = "T2"
    ds.NumberOfSeriesRelatedInstances = 50
    return ds


@pytest.fixture
def nested_dataset():
    ds = Dataset()

    ds.PatientID = "TEST"
    ds.PatientName = "TEST"

    item = Dataset()
    item.CodeValue = "123"
    item.CodingSchemeDesignator = "99TEST"
    item.CodeMeaning = "Test Code"

    ds.AnatomicRegionSequence = [item]

    return ds