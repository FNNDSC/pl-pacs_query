"""
DICOM Identifier Dataset Builder
Converts JSON configuration to pynetdicom Dataset objects
"""

import json
from pydicom.dataset import Dataset
from typing import Dict, Any, Optional


class DICOMIdentifierBuilder:
    """Build DICOM query identifier datasets from JSON configuration"""

    # Standard DICOM query fields for each level
    PATIENT_LEVEL_FIELDS = {
        'PatientName',
        'PatientID',
        'PatientBirthDate',
        'PatientSex',
        'PatientComments'
    }

    STUDY_LEVEL_FIELDS = {
        'PatientName',
        'PatientID',
        'StudyDate',
        'StudyTime',
        'StudyInstanceUID',
        'StudyID',
        'StudyDescription',
        'AccessionNumber',
        'ReferringPhysicianName',
        'ModalitiesInStudy',
        'NumberOfStudyRelatedSeries',
        'NumberOfStudyRelatedInstances'
    }

    SERIES_LEVEL_FIELDS = {
        'StudyInstanceUID',
        'SeriesInstanceUID',
        'SeriesNumber',
        'SeriesDescription',
        'SeriesDate',
        'SeriesTime',
        'Modality',
        'PerformingPhysicianName',
        'NumberOfSeriesRelatedInstances',
        'AnatomicalRegionSequence'
    }

    IMAGE_LEVEL_FIELDS = {
        'StudyInstanceUID',
        'SeriesInstanceUID',
        'SOPInstanceUID',
        'SOPClassUID',
        'InstanceNumber',
        'Rows',
        'Columns',
        'BitsAllocated'
    }

    @staticmethod
    def build_identifier(
            json_config: Dict[str, Any],
            query_level: str = "STUDY",
            empty_optional: bool = True,
            strict: bool = False
    ) -> Dataset:
        """
        Build a DICOM identifier dataset from JSON configuration.

        Args:
            json_config (Dict): JSON dictionary with DICOM tags and values
            query_level (str): Query retrieve level ('PATIENT', 'STUDY', 'SERIES', 'IMAGE')
            empty_optional (bool): Include optional fields as empty strings if not in JSON
            strict (bool): If True, raise error if JSON contains invalid fields for query level

        Returns:
            Dataset: pynetdicom Dataset ready for C-FIND query

        Raises:
            ValueError: If strict=True and invalid fields are found

        Example:
            json_config = {
                "PatientID": "125356",
                "StudyDate": "20211478",
                "StudyInstanceUID": "",
                "Modality": "CT"
            }
            identifier = DICOMIdentifierBuilder.build_identifier(
                json_config,
                query_level="STUDY"
            )
        """
        identifier = Dataset()
        identifier.QueryRetrieveLevel = query_level

        # Get appropriate field list for query level
        if query_level == "PATIENT":
            allowed_fields = DICOMIdentifierBuilder.PATIENT_LEVEL_FIELDS
        elif query_level == "STUDY":
            allowed_fields = DICOMIdentifierBuilder.STUDY_LEVEL_FIELDS
        elif query_level == "SERIES":
            allowed_fields = DICOMIdentifierBuilder.SERIES_LEVEL_FIELDS
        elif query_level == "IMAGE":
            allowed_fields = DICOMIdentifierBuilder.IMAGE_LEVEL_FIELDS
        else:
            raise ValueError(f"Invalid query level: {query_level}")

        # Check for invalid fields if strict mode is enabled
        if strict:
            invalid_fields = set(json_config.keys()) - allowed_fields
            if invalid_fields:
                raise ValueError(
                    f"Invalid fields for query level '{query_level}': {invalid_fields}. "
                    f"Allowed fields: {allowed_fields}"
                )

        # Add fields from JSON config
        for field in allowed_fields:
            if field in json_config:
                value = json_config[field]
                # Set field, converting None to empty string
                setattr(identifier, field, value if value is not None else "")
            elif empty_optional:
                # Include optional fields as empty strings
                setattr(identifier, field, "")

        return identifier

    @staticmethod
    def build_identifier_from_json_file(
            filepath: str,
            query_level: str = "STUDY",
            empty_optional: bool = True
    ) -> Dataset:
        """
        Build identifier dataset from a JSON file.

        Args:
            filepath (str): Path to JSON configuration file
            query_level (str): Query retrieve level
            empty_optional (bool): Include optional fields as empty strings

        Returns:
            Dataset: pynetdicom Dataset
        """
        with open(filepath, 'r') as f:
            json_config = json.load(f)

        return DICOMIdentifierBuilder.build_identifier(
            json_config,
            query_level=query_level,
            empty_optional=empty_optional
        )

    @staticmethod
    def build_identifier_from_json_string(
            json_string: str,
            query_level: str = "STUDY",
            empty_optional: bool = True
    ) -> Dataset:
        """
        Build identifier dataset from a JSON string.

        Args:
            json_string (str): JSON string with DICOM tags
            query_level (str): Query retrieve level
            empty_optional (bool): Include optional fields as empty strings

        Returns:
            Dataset: pynetdicom Dataset
        """
        json_config = json.loads(json_string)

        return DICOMIdentifierBuilder.build_identifier(
            json_config,
            query_level=query_level,
            empty_optional=empty_optional
        )
