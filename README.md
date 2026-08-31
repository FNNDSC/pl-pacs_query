# A ChRIS plugin to query a remote PACS

[![Version](https://img.shields.io/docker/v/fnndsc/pl-pacs_query?sort=semver)](https://hub.docker.com/r/fnndsc/pl-pacs_query)
[![MIT License](https://img.shields.io/github/license/fnndsc/pl-pacs_query)](https://github.com/FNNDSC/pl-pacs_query/blob/main/LICENSE)
[![ci](https://github.com/FNNDSC/pl-pacs_query/actions/workflows/ci.yml/badge.svg)](https://github.com/FNNDSC/pl-pacs_query/actions/workflows/ci.yml)

`pl-pacs_query` is a [_ChRIS_](https://chrisproject.org/)
_ds_ plugin that queries a remote PACS using `pfdcm` and returns structured
metadata describing available DICOM studies or series.  

The plugin communicates directly with a PACS using DICOM C-FIND through
`pynetdicom`. Queries are performed hierarchically: matching studies are
identified first, followed by a series-level query for each matching study.

The query results are written to the output directory as JSON files for
downstream processing.

## Abstract

Querying a PACS for available imaging data is commonly the first step in
automated DICOM retrieval and processing workflows.

`pl-pacs_query` provides this functionality within a ChRIS pipeline by
performing DICOM C-FIND operations against a configured remote PACS.

Because many PACS implementations do not support relational C-FIND queries,
the plugin performs hierarchical Query/Retrieve:

1. A **STUDY-level C-FIND** is performed using the supplied PACS directive.
2. The `StudyInstanceUID` is collected from each matching study.
3. A **SERIES-level C-FIND** is performed separately for each study, scoped by
   its `StudyInstanceUID`.
4. The resulting series metadata is converted to JSON-compatible dictionaries.
5. `pfdcm.autocomplete_directive()` combines the original query directive with
   the PACS response and calculates the expected number of DICOM instances.
6. The generated response is written to the plugin output directory as JSON.

This hierarchical approach avoids relying on PACS support for relational
queries and ensures that series queries are scoped to an exact parent study.

## Installation

`pl-pacs_query` is a _[ChRIS](https://chrisproject.org/) plugin_, meaning it can
run from either within _ChRIS_ or the command-line.

## Command-Line Arguments

### Positional Arguments

| Argument | Description |
|--------|------------|
| `inputdir` | Directory containing input files (read-only). May be empty. |
| `outputdir` | Directory where query results will be written. |

### PACS Connection Arguments

| Option | Required | Description |
|---|---|---|
| `--src-aet` | Yes | Called AE Title of the remote PACS. |
| `--src-ip` | Yes | Hostname or IP address of the remote PACS. |
| `--src-port` | Yes | DICOM port of the remote PACS. |
| `--dst-aet` | Yes | Calling AE Title used by `pl-pacs_query`. This AE Title generally must be known/authorized by the PACS. |

### Query Arguments

| Option | Default | Description |
|---|---|---|
| `--PACSdirective` | `""` | JSON string containing the PACS query criteria. |
| `--reportName` | `""` | Name of the output report without the `.json` extension. If omitted, a deterministic hash-based report name is generated. |
| `--query-model` | `study` | DICOM Query/Retrieve information model. Supported values are `study` and `patient`. |
| `-V`, `--version` | — | Print the plugin version and exit. |

## PACS Directive

`--PACSdirective` accepts a JSON object describing the PACS query.

For example:

```json
{
    "PatientID": "TEST",
    "StudyDate": "20251027"
}
```
When passed on the command line, quote the complete JSON string:

```shell
--PACSdirective '{"PatientID":"TEST","StudyDate":"20251027"}'
```

The directive is sanitized using `pfdcm` before being converted into a DICOM
query identifier.

## Query Workflow

The plugin uses a two-stage hierarchical C-FIND workflow.

### 1. STUDY Query

The supplied PACS directive is converted into a STUDY-level DICOM identifier.

Conceptually:

```text
PatientID = TEST
StudyDate = 20251027
QueryRetrieveLevel = STUDY
```

The remote PACS returns zero or more matching studies.

For every matching study, the plugin obtains its:

```text
StudyInstanceUID
```

### 2. SERIES Query

For every returned study, a second C-FIND is performed:

```text
QueryRetrieveLevel = SERIES
StudyInstanceUID = <matching study UID>
```

This ensures that each SERIES query is scoped to a specific parent study.

The series responses are converted to dictionaries and collected into the
search response used by `pfdcm.autocomplete_directive()`.

## Output

The plugin writes a JSON report to `outputdir`.

When `--reportName` is supplied:

```shell
--reportName search_results
```

the output is:

```text
search_results.json
```

If `--reportName` is omitted, the plugin generates a deterministic MD5 hash
from the generated response:

```text
search_results_<hash>.json
```

For example:

```text
outgoing/
└── search_results_a2f4c80d20a74c42b79c47cf219cf15f.json
```

A result may contain fields such as:

```json
[
    {
        "PatientID": "TEST",
        "PatientName": "TEST",
        "StudyDate": "20251027",
        "StudyInstanceUID": "1.2.3.4.5",
        "SeriesInstanceUID": "1.2.3.4.5.1",
        "SeriesNumber": "1",
        "SeriesDescription": "T1",
        "Modality": "MR",
        "NumberOfSeriesRelatedInstances": "100"
    }
]
```

The exact fields returned depend on the remote PACS and the DICOM attributes
included in its C-FIND responses.

---

## Local Usage

To get started with local command-line usage, use [Apptainer](https://apptainer.org/)
(a.k.a. Singularity) to run `pl-pacs_query` as a container:

```shell
apptainer exec docker://fnndsc/pl-pacs_query pacs_query [--args values...] input/ output/
```

To print its available options, run:

```shell
apptainer exec docker://fnndsc/pl-pacs_query pacs_query --help
```

## Examples

`pacs_query` requires two positional arguments: a directory containing
input data, and a directory where to create output data.
First, create the input directory and move input data into it.

```shell
mkdir incoming/ outgoing/
mv some.dat other.dat incoming/
apptainer exec docker://fnndsc/pl-pacs_query:latest \
    pacs_query \
    --src-aet TEST_PACS \
    --src-ip 127.0.0.1 \
    --src-port 104 \
    --dst-aet TEST_CLIENT \
    --PACSdirective '{"PatientID":"TEST","StudyDate":"20251027"}' \
    --reportName search_results \
    incoming/ outgoing/
```

## Development

Instructions for developers.

### Building

Build a local container image:

```shell
docker build -t localhost/fnndsc/pl-pacs_query .
```

### Running

Mount the source code `pacs_query.py` into a container to try out changes without rebuild.

```shell
docker run --rm \
    -v "$PWD/incoming:/incoming:ro" \
    -v "$PWD/outgoing:/outgoing:rw" \
    local/pl-pacs_query \
    pacs_query \
    --src-aet TEST_PACS \
    --src-ip PACS_HOST \
    --src-port 104 \
    --dst-aet TEST_CLIENT \
    --PACSdirective '{"PatientID":"TEST","StudyDate":"20251027"}' \
    --reportName search_results \
    /incoming /outgoing
```
After a successful query:

```text
outgoing/
└── search_results.json

> **Note:** The PACS must be reachable from inside the container. The calling
> AE Title supplied with `--dst-aet` may also need to be registered or
> authorized by the remote PACS.

### Testing

Run unit tests using `pytest`.
It's recommended to rebuild the image to ensure that sources are up-to-date.
Use the option `--build-arg extras_require=dev` to install extra dependencies for testing.

```shell
docker build -t localhost/fnndsc/pl-pacs_query:dev --build-arg extras_require=dev .
docker run --rm -it localhost/fnndsc/pl-pacs_query:dev pytest
```

## Release

Steps for release can be automated by [Github Actions](.github/workflows/ci.yml).
This section is about how to do those steps manually.

### Increase Version Number

Increase the version number in `setup.py` and commit this file.

### Push Container Image

Build and push an image tagged by the version. For example, for version `1.2.3`:

```
docker build -t docker.io/fnndsc/pl-pacs_query:1.2.3 .
docker push docker.io/fnndsc/pl-pacs_query:1.2.3
```

### Get JSON Representation

Run [`chris_plugin_info`](https://github.com/FNNDSC/chris_plugin#usage)
to produce a JSON description of this plugin, which can be uploaded to _ChRIS_.

```shell
docker run --rm docker.io/fnndsc/pl-pacs_query:1.2.3 chris_plugin_info -d docker.io/fnndsc/pl-pacs_query:1.2.3 > chris_plugin_info.json
```

Intructions on how to upload the plugin to _ChRIS_ can be found here:
https://chrisproject.org/docs/tutorials/upload_plugin

