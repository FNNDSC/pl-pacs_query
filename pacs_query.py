#!/usr/bin/env python

from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
from loguru import logger
from chris_plugin import chris_plugin, PathMapper
import hashlib
import pfdcm
import json
import sys
import pprint
import os
from dicom_identifier_builder import DICOMIdentifierBuilder
from pynetdicom import AE
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
)
from pydicom.dataset import Dataset
from pydicom.datadict import keyword_for_tag

LOG = logger.debug

logger_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> │ "
    "<level>{level: <5}</level> │ "
    "<yellow>{name: >28}</yellow>::"
    "<cyan>{function: <30}</cyan> @"
    "<cyan>{line: <4}</cyan> ║ "
    "<level>{message}</level>"
)
logger.remove()
logger.add(sys.stderr, format=logger_format)
__version__ = '1.0.9'

DISPLAY_TITLE = r"""
       _                                                          
      | |                                                         
 _ __ | |______ _ __   __ _  ___ ___   __ _ _   _  ___ _ __ _   _ 
| '_ \| |______| '_ \ / _` |/ __/ __| / _` | | | |/ _ \ '__| | | |
| |_) | |      | |_) | (_| | (__\__ \| (_| | |_| |  __/ |  | |_| |
| .__/|_|      | .__/ \__,_|\___|___/ \__, |\__,_|\___|_|   \__, |
| |            | |                ______ | |                 __/ |
|_|            |_|               |______||_|                |___/ 
"""


parser = ArgumentParser(description='A ChRIS plugin to query PACS using pfdcm',
                        formatter_class=ArgumentDefaultsHelpFormatter)

# PACS / network
parser.add_argument("--src-aet", required=True, help="Called AET  (PACS AE title)")
parser.add_argument("--src-ip", required=True, help="PACS host / IP address")
parser.add_argument("--src-port", required=True, type=int, help="PACS DICOM port")
parser.add_argument("--dst-aet", required=True, help="Calling AET (our AE title, must be registered on PACS)")
parser.add_argument(
    '--PACSdirective',
    default='',
    type=str,
    help='directive to query the PACS'
)
parser.add_argument(
    "--reportName",
    default="",
    help="name of the output report containing search results (excluding file extension)"
)
parser.add_argument(
        "--query-model",
        default="study",
        choices=["study", "patient"],
        help="Query/Retrieve model",
    )
parser.add_argument('-V', '--version', action='version',
                    version=f'%(prog)s {__version__}')


# The main function of this *ChRIS* plugin is denoted by this ``@chris_plugin`` "decorator."
# Some metadata about the plugin is specified here. There is more metadata specified in setup.py.
#
# documentation: https://fnndsc.github.io/chris_plugin/chris_plugin.html#chris_plugin
@chris_plugin(
    parser=parser,
    title='A ChRIS plugin to query a remote PACS',
    category='',                 # ref. https://chrisstore.co/plugins
    min_memory_limit='100Mi',    # supported units: Mi, Gi
    min_cpu_limit='1000m',       # millicores, e.g. "1000m" = 1 CPU core
    min_gpu_limit=0              # set min_gpu_limit=1 to enable GPU
)
def main(options: Namespace, inputdir: Path, outputdir: Path):
    """
    *ChRIS* plugins usually have two positional arguments: an **input directory** containing
    input files and an **output directory** where to write output files. Command-line arguments
    are passed to this main method implicitly when ``main()`` is called below without parameters.

    :param options: non-positional arguments parsed by the parser given to @chris_plugin
    :param inputdir: directory containing (read-only) input files
    :param outputdir: directory where to write output files
    """
    LOG(DISPLAY_TITLE)

    directive = json.loads(options.PACSdirective)

    search_directive, _ = pfdcm.sanitize(
        directive
    )

    search_response = cfind(
        options,
        search_directive,
    )

    generated_response, file_count = (
        pfdcm.autocomplete_directive(
            directive,
            search_response,
        )
    )

    LOG(pprint.pformat(generated_response))
    LOG(f"file count is : {file_count}")

    op_json_file_path = os.path.join(
        options.outputdir,
        f"search_results_{dict_to_hash(generated_response)}.json",
    )

    if options.reportName:
        op_json_file_path = os.path.join(
            options.outputdir,
            f"{options.reportName}.json",
        )

    LOG(op_json_file_path)

    with open(
        op_json_file_path,
        "w",
        encoding="utf-8",
    ) as jsonf:
        jsonf.write(
            json.dumps(
                generated_response,
                indent=4,
            )
        )

# ---------------------------------------------------------------------------
# C-FIND
# ---------------------------------------------------------------------------
def cfind(args, search_dataset) -> dict:
    """Query the PACS and return a list of matching series-level datasets.

    FIX: this SCP (like most that don't negotiate DICOM "relational queries")
    only supports *hierarchical* C-FIND: a query at SERIES level must be scoped
    by an exact parent StudyInstanceUID. Sending PatientID/StudyDate alone at the
    SERIES level (with StudyInstanceUID blank) asks for "every series across every
    matching study" -- unscoped enough that the SCP refuses it with 0xA700, just
    like the STUDY-level query did before it had real matching keys.

    So this now runs two passes:
      1. STUDY-level C-FIND using the caller's search_dataset -> get matching
         studies, each with a StudyInstanceUID.
      2. SERIES-level C-FIND per study, scoped by that StudyInstanceUID -> get the
         series-level records (with NumberOfSeriesRelatedInstances) that
         pfdcm.autocomplete_directive() actually needs.
    """
    ae = AE(ae_title=args.dst_aet)

    # Try Study-root first, fall back to Patient-root
    find_model = (
        StudyRootQueryRetrieveInformationModelFind
        if args.query_model == "study"
        else PatientRootQueryRetrieveInformationModelFind
    )
    ae.add_requested_context(find_model)

    # FIX: logger doesn't do %-style lazy interpolation like stdlib logging.Logger does,
    # so the old "%s:%d ... %s", arg1, arg2, arg3 form silently drops the args and prints
    # the raw placeholders. Use f-strings so the values are actually rendered.
    logger.info(
        f"C-FIND → {args.src_ip}:{args.src_port}  (src-AET: {args.src_aet})"
    )

    assoc = ae.associate(args.src_ip, args.src_port, ae_title=args.src_aet)
    if not assoc.is_established:
        logger.error("C-FIND association rejected or failed")
        return []

    results = []
    try:
        # ---------------- Pass 1: STUDY level ----------------
        study_identifier = DICOMIdentifierBuilder.build_identifier(search_dataset, "STUDY")
        logger.debug(f"C-FIND (STUDY) identifier being sent:\n{study_identifier}")

        studies = []
        study_responses = assoc.send_c_find(study_identifier, find_model)
        for status, dataset in study_responses:
            if status and status.Status in (0xFF00, 0xFF01):  # Pending
                if dataset:
                    studies.append(dataset)
            elif status and status.Status == 0x0000:
                logger.info(f"STUDY C-FIND complete — {len(studies)} studies found")
            else:
                _log_cfind_failure(status, dataset)

        # ---------------- Pass 2: SERIES level, per study ----------------
        for study_ds in studies:
            study_uid = getattr(study_ds, "StudyInstanceUID", None)
            if not study_uid:
                logger.warning("Study result missing StudyInstanceUID, skipping series lookup")
                continue

            series_identifier = DICOMIdentifierBuilder.build_identifier(
                {"StudyInstanceUID": study_uid}, "SERIES"
            )
            logger.debug(f"C-FIND (SERIES) identifier being sent:\n{series_identifier}")

            series_responses = assoc.send_c_find(series_identifier, find_model)
            series_count = 0
            for status, dataset in series_responses:
                if status and status.Status in (0xFF00, 0xFF01):  # Pending
                    if dataset:
                        results.append(dataset_to_dict(dataset))
                        series_count += 1
                elif status and status.Status == 0x0000:
                    logger.info(
                        f"SERIES C-FIND complete for study {study_uid} — {series_count} series found"
                    )
                else:
                    _log_cfind_failure(status, dataset)
    finally:
        assoc.release()

    # Convert to JSON
    results_json = json.dumps(results, indent=2)
    return json.loads(results_json)


def _log_cfind_failure(status, dataset):
    """Log a non-success C-FIND status, including any SCP-provided ErrorComment."""
    status_code = status.Status if status else -1
    logger.warning(f"C-FIND unexpected status: 0x{status_code:04X}")

    # FIX: on refusal/failure statuses, the SCP often includes an (0000,0902)
    # ErrorComment (and sometimes OffendingElement) in the response explaining why --
    # e.g. AE title not registered/authorized, unsupported matching key, missing
    # parent unique key, etc. We were discarding that dataset entirely and only
    # looking at the bare status code.
    error_comment = getattr(dataset, "ErrorComment", None) if dataset else None
    if error_comment:
        logger.warning(f"C-FIND SCP error comment: {error_comment}")
    if dataset:
        logger.debug(f"C-FIND failure response dataset:\n{dataset}")


def dataset_to_dict(dataset, include_tags=False):
    """
    Convert DICOM dataset to dictionary with readable tag names.
    Handles sequences recursively.

    Args:
        dataset: DICOM dataset
        include_tags: If True, include hex tag codes in keys

    Returns:
        Dictionary with DICOM data
    """
    dataset_dict = {}

    for elem in dataset:
        tag_name = keyword_for_tag(elem.tag) or str(elem.tag)

        # Handle sequences (nested datasets)
        if elem.VR == 'SQ':
            sequence_list = []
            for item in elem.value:
                if isinstance(item, Dataset):
                    # Recursively convert nested datasets
                    sequence_list.append(dataset_to_dict(item, include_tags))
                else:
                    sequence_list.append(str(item))

            if include_tags:
                dataset_dict[f"{tag_name} ({elem.tag})"] = sequence_list
            else:
                dataset_dict[tag_name] = sequence_list
        else:
            # Regular element: convert to string
            value = str(elem.value)

            if include_tags:
                dataset_dict[f"{tag_name} ({elem.tag})"] = value
            else:
                dataset_dict[tag_name] = value

    return dataset_dict


def dict_to_hash(data: dict) -> str:
    # Convert dict to a JSON string with sorted keys for consistency
    data_str = json.dumps(data, sort_keys=True)
    # Encode to bytes
    hash_request = hashlib.md5(data_str.encode('utf-8'))
    # Return the hex digest
    return hash_request.hexdigest()


if __name__ == '__main__':
    main()