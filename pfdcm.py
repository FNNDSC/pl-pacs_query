import requests
from loguru import logger
import sys
import copy
from collections import ChainMap
import json

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

def health_check(url: str):
    pfdcm_about_api = f'{url}about/'
    headers = {'Content-Type': 'application/json', 'accept': 'application/json'}
    try:
        response = requests.get(pfdcm_about_api, headers=headers)
        return response
    except Exception as er:
        raise Exception("Connection to pfdcm could not be established.")


def get_pfdcm_status(directive: dict, url: str, pacs_name: str):
    """
    Get the status of PACS from `pfdcm`
    by running the synchronous API of `pfdcm`
    """

    pfdcm_status_url = f'{url}PACS/sync/pypx/'
    headers = {'Content-Type': 'application/json', 'accept': 'application/json'}

    body = {
        "PACSservice": {
            "value": pacs_name
        },
        "listenerService": {
            "value": "default"
        },
        "PACSdirective": {
            "withFeedBack": True,
            "then": "status",
            "thenArgs": '',
            "dblogbasepath": '/home/dicom/log',
            "json_response": False
        }
    }
    body["PACSdirective"].update(directive)
    LOG(body)

    try:
        response = requests.post(pfdcm_status_url, json=body, headers=headers)
        d_response = json.loads(response.text)
        if d_response['status']: return d_response
        else: raise Exception(d_response['message'])
    except Exception as ex:
        LOG(ex)