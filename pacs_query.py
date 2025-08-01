#!/usr/bin/env python

from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
from pflog import pflog
from loguru import logger
from chris_plugin import chris_plugin, PathMapper
import pfdcm
import json
import sys
import pprint
import os
import cube_pacs_api
from datetime import datetime

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
__version__ = '1.0.6'

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

parser.add_argument(
    '--PACSurl',
    default='',
    type=str,
    help='endpoint URL of pfdcm'
)
parser.add_argument(
    '--PACSname',
    default='MINICHRISORTHANC',
    type=str,
    help='name of the PACS'
)
parser.add_argument(
    '--PACSdirective',
    default='',
    type=str,
    help='directive to query the PACS'
)
parser.add_argument(
    "--CUBEurl",
    default="http://localhost:8000/",
    help="CUBE URL. Please exclude api version in the url endpoint."
)
parser.add_argument(
    "--CUBEuser",
    default="chris",
    help="CUBE/ChRIS username"
)
parser.add_argument(
    "--CUBEpassword",
    default="chris1234",
    help="CUBE/ChRIS password"
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
    search_directive,_ = pfdcm.sanitize(directive)

    # generate a unique title based on timestamp
    prefix = "pacs_query"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    title =  f"{prefix}_{timestamp}"

    # search_response = pfdcm.get_pfdcm_status(search_directive, options.PACSurl, options.PACSname)
    search_response = cube_pacs_api.get_pacs_status(options.CUBEuser,options.CUBEpassword,title, search_directive,options.CUBEurl)
    generated_response, file_count = cube_pacs_api.autocomplete_directive(directive, search_response)

    # LOG(pprint.pformat(search_response['pypx']['data']))
    LOG(pprint.pformat(generated_response))
    LOG(f"file count is : {file_count}")
    op_json_file_path  = os.path.join(options.outputdir,"search_results.json")
    # Open a json writer, and use the json.dumps()
    # function to dump data
    with open(op_json_file_path, 'w', encoding='utf-8') as jsonf:
        jsonf.write(json.dumps(generated_response, indent=4))


if __name__ == '__main__':
    main()
