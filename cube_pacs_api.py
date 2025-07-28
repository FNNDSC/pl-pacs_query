import base64
import json
import zlib
import requests
from requests.auth import HTTPBasicAuth
import time
import sys
from loguru import logger
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

def get_headers():
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*"
    }


def submit_query(base_url, auth, title, query_str):
    url = f"{base_url}/api/v1/pacs/1/queries/"
    data = {
        "title": title,
        "query": json.dumps(query_str)
    }
    LOG(data)

    response = requests.post(url, data=data, headers=get_headers(), auth=auth)
    if response.status_code == 400:
        error_msg = response.json().get("collection", {}).get("error", {}).get("message", "")
        if "already registered" in error_msg:
            LOG(f"[INFO] Query title '{title}' already registered. Searching existing queries...")
            return find_query_id_by_title(base_url, auth, title)
        else:
            raise Exception(f"[ERROR] 400 Bad Request: {error_msg}")

    response.raise_for_status()
    return extract_id_from_items(response.json())


def find_query_id_by_title(base_url, auth, title):
    url = f"{base_url}/api/v1/pacs/1/queries/"
    response = requests.get(url, auth=auth)
    response.raise_for_status()

    items = response.json().get("collection", {}).get("items", [])
    for item in items:
        data_fields = item.get("data", [])
        title_field = next((f for f in data_fields if f["name"] == "title" and f["value"] == title), None)
        if title_field:
            id_field = next((f for f in data_fields if f["name"] == "id"), None)
            if id_field:
                return id_field["value"]
    raise Exception(f"[ERROR] Query with title '{title}' not found.")


def extract_id_from_items(json_response):
    items = json_response.get("collection", {}).get("items", [])
    for item in items:
        for field in item.get("data", []):
            if field.get("name") == "id":
                return field.get("value")
    raise Exception("[ERROR] No query ID found in response.")


def fetch_query_result(base_url, auth, query_id, timeout=60, interval=3):
    url = f"{base_url}/api/v1/pacs/queries/{query_id}/"
    start_time = time.time()

    while True:
        response = requests.get(url, auth=auth)
        response.raise_for_status()

        items = response.json().get("collection", {}).get("items", [])
        status = None
        result = None

        for item in items:
            for field in item.get("data", []):
                if field.get("name") == "status":
                    status = field.get("value")
                elif field.get("name") == "result":
                    result = field.get("value")

        if status == "succeeded":
            if result is not None:
                return result
            else:
                raise Exception("[ERROR] 'result' not found despite status succeeded.")

        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(f"Timeout waiting for query to succeed. Last status: {status}")

        LOG(f"[INFO] Current status: {status}. Retrying in {interval}s...")
        time.sleep(interval)



def decode_and_decompress(encoded_str):
    if len(encoded_str) == 0:
        return ""
    decoded = base64.b64decode(encoded_str)
    try:
        # Try standard zlib decompress
        decompressed = zlib.decompress(decoded)
    except zlib.error:
        try:
            # Fallback to raw deflate
            decompressed = zlib.decompress(decoded, wbits=-zlib.MAX_WBITS)
        except zlib.error as e:
            raise RuntimeError(f"Decompression failed: {e}")

    try:
        # Decode bytes to UTF-8 string
        text = decompressed.decode("utf-8")
        # Try to load and pretty-print JSON
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2)
    except (UnicodeDecodeError, json.JSONDecodeError):
        # Return raw string if not valid JSON
        return decompressed.decode("utf-8")

def get_pacs_status(username, password, title, query, base_url):
    auth = HTTPBasicAuth(username, password)

    try:
        LOG("[INFO] Submitting or reusing PACS query...")
        query_id = submit_query(base_url, auth, title, query)
        LOG(f"[INFO] Using query ID: {query_id}")

        LOG("[INFO] Fetching query result...")
        result_encoded = fetch_query_result(base_url, auth, query_id )

        LOG("[INFO] Decoding and decompressing result...")
        result = decode_and_decompress(result_encoded)
        if result == "" : return {}
        # print("Query Result (.jq format):")
        # print(result)
        return json.loads(result)

    except Exception as e:
        print(e)

def autocomplete_directive(directive: dict, d_response: dict) -> (list,int):
    """
    Autocomplete certain fields in the search directive using response
    object from pfdcm
    """
    file_count = 0
    res: list = []

    # get the count of all matching files inside PACS
    # we will be using this count to verify file registration
    # in CUBE

    for l_series in d_response:
        for series in l_series["series"]:
            ser = {}

            # iteratively check for all search fields and update the search record simultaneously
            # with SeriesInstanceUID and StudyInstanceUID
            flag = True
            for key in directive.keys():
                if series.get(key) and directive[key].lower() in series[key]["value"].lower():
                    flag = flag and True
                else:
                    flag = flag and False
            if flag:
                for label in series:
                    ser[label] = series[label]["value"]
                res.append(ser)
                file_count += int(series["NumberOfSeriesRelatedInstances"]["value"])
            else:
                continue

    # _.update(partial_directive)
    return res, file_count

