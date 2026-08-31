"""
DICOM Identifier Dataset Builder
Converts JSON configuration to pynetdicom Dataset objects
"""

import json
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from typing import Dict, Any


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
        # FIX: real DICOM keyword for tag (0008,2218) is "AnatomicRegionSequence"
        # (no "al"). The misspelled version isn't recognized by pydicom, so setattr()
        # silently created a plain Python attribute instead of a DICOM element -- it
        # was never actually included in the identifier sent to the SCP. Correcting
        # the keyword makes this field real (and stops the recurring pydicom warning).
        'AnatomicRegionSequence'
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

    # FIX: fields whose DICOM VR is SQ (Sequence). These can NEVER be assigned a plain
    # string like "" — pydicom needs a Sequence of Dataset objects. Assigning "" produces
    # a malformed identifier, which is what was triggering the pydicom "camel case
    # attribute not in keyword dictionary" warning and causing the SCP to refuse the
    # whole C-FIND with status 0xA700 (Out of Resources) instead of just returning zero
    # matches.
    SEQUENCE_FIELDS = {
        'AnatomicRegionSequence',
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

        # Get appropriate field list for query level.
        # FIX: per the DICOM Study Root Q/R model, matching keys are hierarchical --
        # a query at SERIES level can (and should) still carry Patient- and Study-level
        # attributes (PatientID, StudyDate, AccessionNumber, etc.) as additional
        # matching keys, not just SERIES-specific fields. The previous flat, per-level
        # whitelist silently dropped those higher-level identifying keys whenever
        # query_level was "SERIES", producing an effectively unconstrained query that
        # the SCP refused with 0xA700 (Out of Resources). Union the field sets by
        # hierarchy instead of treating each level's fields as mutually exclusive.
        if query_level == "PATIENT":
            allowed_fields = DICOMIdentifierBuilder.PATIENT_LEVEL_FIELDS
        elif query_level == "STUDY":
            allowed_fields = (
                DICOMIdentifierBuilder.PATIENT_LEVEL_FIELDS
                | DICOMIdentifierBuilder.STUDY_LEVEL_FIELDS
            )
        elif query_level == "SERIES":
            allowed_fields = (
                DICOMIdentifierBuilder.PATIENT_LEVEL_FIELDS
                | DICOMIdentifierBuilder.STUDY_LEVEL_FIELDS
                | DICOMIdentifierBuilder.SERIES_LEVEL_FIELDS
            )
        elif query_level == "IMAGE":
            allowed_fields = (
                DICOMIdentifierBuilder.PATIENT_LEVEL_FIELDS
                | DICOMIdentifierBuilder.STUDY_LEVEL_FIELDS
                | DICOMIdentifierBuilder.SERIES_LEVEL_FIELDS
                | DICOMIdentifierBuilder.IMAGE_LEVEL_FIELDS
            )
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
            is_sequence_field = field in DICOMIdentifierBuilder.SEQUENCE_FIELDS

            if field in json_config:
                value = json_config[field]

                if is_sequence_field:
                    # FIX: build a proper Sequence of Datasets instead of assigning
                    # a raw string/dict. Accepts: None/[] -> empty Sequence (universal
                    # matching), a single dict -> one-item Sequence, or a list of dicts
                    # -> multi-item Sequence.
                    setattr(identifier, field, DICOMIdentifierBuilder._to_sequence(value))
                else:
                    # Set field, converting None to empty string
                    setattr(identifier, field, value if value is not None else "")

            elif empty_optional:
                if is_sequence_field:
                    # FIX: empty Sequence, not empty string, for universal matching
                    # on a Sequence-VR element.
                    setattr(identifier, field, Sequence())
                else:
                    # Include optional fields as empty strings
                    setattr(identifier, field, "")

        return identifier

    @staticmethod
    def _to_sequence(value: Any) -> Sequence:
        """
        Normalize a JSON value into a pydicom Sequence for an SQ-VR element.

        Args:
            value: None, a dict (single item), or a list of dicts (multiple items).
                   Each dict maps DICOM keywords to values for that sequence item.

        Returns:
            Sequence: a pydicom Sequence containing zero or more Datasets.
        """
        if value is None:
            return Sequence()

        if isinstance(value, dict):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            # Defensive fallback: an unexpected scalar (e.g. "") for a sequence field.
            # Treat it as "no constraint" rather than producing an invalid element.
            return Sequence()

        datasets = []
        for item in items:
            if not isinstance(item, dict):
                continue
            ds = Dataset()
            for key, val in item.items():
                setattr(ds, key, val if val is not None else "")
            datasets.append(ds)

        return Sequence(datasets)

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