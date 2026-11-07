# Organize Exam Questions

A NanoAgent plugin whose task, `transcribe-exams`, organizes the original
August 2026 New York Algebra II Regents exam into JSON. The agent reads
[the bundled PDF](src/plugin/data/algtwo-82026-exam.pdf) in page order and groups
its text by question and subquestion. PDFium extracts embedded text locally;
the agent uses a text-only model. The plugin performs no OCR and makes no
network requests.

## Tools

| Tool | Does | Code |
|---|---|---|
| `read_pdf` | Returns the exam's page count and embedded text for one to five distinct, increasing, one-based page numbers. The bundled exam has 28 pages; page 24 has no embedded text and returns an empty string | `src/plugin/transcribe.py` |
| `save_transcription` | Writes the selected interval and its complete questions as UTF-8 JSON to `transcriptions/questions.json` in the workspace, replacing any previous save, and returns its path and full transcription | `src/plugin/transcribe.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `transcribe-exams` | Reads the exam, groups questions and their separate response prompts, saves the selected interval, and returns its path and full transcription. Takes `{"start_page": 1, "end_page": 5}` as input | `agent`, with `read_pdf` and `save_transcription` |

### The task

Each task takes an inclusive one-based PDF page interval, `start_page` through
`end_page`, of one to five pages within the 28-page source. The agent reads only
that interval in increasing order. To process the exam, run intervals such as
1–5, 6–10, 11–15, 16–20, 21–25, and 26–28 separately.

Only questions fully contained in the selected interval are included. Questions
cut off at either boundary are omitted, including their partial subquestions.
Question 36 spans pages 22–23 and requires both pages. Use an overlapping
interval when necessary to capture a question spanning a batch boundary.
Each question records all its source PDF pages in `pages`. Shared setup,
options, and single-response instructions go in `prompt`; separately printed
response prompts go in `subquestions`. Booklet instructions, headers, footers,
blank work space, and reference sheets are skipped. Intervals with no complete
questions save an empty questions object.

The saved format is illustrated below (a partial example):

```json
{
  "start_page": 2,
  "end_page": 2,
  "questions": {
    "1": {"prompt": "Question 1 text and choices", "subquestions": [], "pages": [2]},
    "2": {"prompt": "Question 2 text and choices", "subquestions": [], "pages": [2]},
    "3": {"prompt": "Question 3 text and choices", "subquestions": [], "pages": [2]}
  }
}
```

The task returns `{"path": "transcriptions/questions.json", "transcription": {...}}`,
where `transcription` contains the full saved JSON shown above, including the page
interval and questions, so it can be read directly in the result. Diagrams, tables,
and math may lose information during text extraction: the agent preserves
available text without solving questions or reconstructing missing visuals.

### Verification

The verifier checks only complete questions within the requested interval,
using a fixed question-to-page reference in `contract.py`. It requires
the saved interval to match the task input and rejects missing, unexpected,
cut-off, or incorrectly attributed questions. Questions 34, 35, and 36 have
three, two, and four subquestions respectively; other questions have none.
Structural failures score zero. Reference prose fragments for the selected
questions account for 20% of the score, normalized to that interval. Matching
ignores case, punctuation, and wrapping. These spot checks do not establish
full transcription accuracy.

Tool checks confirm requested page order and ranges, and that the saved JSON
matches the save input. File checks refuse duplicate JSON keys and symbolic
links in the output path. Saves use a temporary file followed by replacement.

## Layout

```text
├── nanoagent.yaml       # manifest, permissions, tools, and task instructions
├── contract.py          # declarations only: enums, types, constants, and page reference
├── pyproject.toml       # package and development dependencies
├── uv.lock              # locked dependencies
├── src/plugin/          # MCP server, tools, and runtime input validation
│   └── data/            # bundled original exam PDF
├── verifier/            # independent validation, saved-file checks, and task scoring
├── tests/               # PDF reads, saves, file validation, MCP, and verifier tests
├── ui/                  # renderer entry point and styles
└── product/             # catalog description and icon
```

### Upload compatibility

`contract.py` contains declarations only. Its `QUESTION_PAGES` reference is a
literal mapping; functions and computed mappings belong outside the contract.
Runtime input checks live in `src/plugin/validation.py`. The verifier has its
own checks in `verifier/validation.py` because it cannot import plugin runtime
modules. Keep these checks consistent when changing validation rules. Verifier
modules use relative imports for their own helpers and import shared constants
and types from `contract`.

## Develop and run

Use Python 3.12 or newer and `uv`. From the plugin root:

```sh
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest
uv run --frozen --extra dev ruff check .
```

Load `nanoagent.yaml` in NanoAgent and run `transcribe-exams` with `{"start_page": 1, "end_page": 5}`.
NanoAgent starts `uv run --frozen python -m plugin` and passes the writable
workspace as `NANOAGENT_WORKSPACE`. Review `transcriptions/questions.json`
in that workspace and the task's verification report.

The tests cover all 28 PDF pages, invalid requests, Unicode saves, repeated and
failed writes, symbolic links, malformed JSON, task scoring, and MCP calls.
The page reference lives in `contract.py`; scoring anchors live in
`verifier/transcribe.py`. Update both if the bundled source changes.
Each save replaces the previous interval at the same output path; retain a copy
before running another interval if you need all interval files.
