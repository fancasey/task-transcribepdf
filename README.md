# Organize Exam Questions

A NanoAgent plugin whose task, `transcribe-exams`, organizes the original
August 2026 New York Algebra II Regents exam into JSON. The agent reads
[the bundled PDF](src/plugin/data/algtwo-82026-exam.pdf) in page order and groups
its text by question and subquestion. PDFium extracts embedded text locally;
the agent uses a text-only model, with no OCR or network requests.

## Tools

| Tool | Does | Code |
|---|---|---|
| `read_pdf` | Returns the exam's page count and embedded text for one to three distinct, increasing, one-based page numbers. The bundled exam has 28 pages; page 24 has no embedded text and returns an empty string | `src/plugin/transcribe.py` |
| `save_transcription` | Writes the questions object as UTF-8 JSON to `transcriptions/questions.json` in the workspace, replacing any previous save, and returns its path | `src/plugin/transcribe.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `transcribe-exams` | Reads the exam, groups questions and their separate response prompts, saves the complete transcription, and returns its path. Takes `{}` as input | `agent`, with `read_pdf` and `save_transcription` |

### The task

The agent reads in increasing page order, up to three pages per call. It keeps
shared setup, multiple-choice options, and instructions for a single response
in `prompt`; separately printed response prompts go in `subquestions`, in
order. Continued questions are joined across pages. Booklet instructions,
headers, footers, blank work space, and reference sheets are skipped.

The saved format is illustrated below (a partial example):

```json
{
  "questions": {
    "1": {"prompt": "Question text and answer choices", "subquestions": []},
    "34": {"prompt": "Shared setup", "subquestions": ["First prompt", "Second prompt", "Third prompt"]}
  }
}
```

The task returns `{"path": "transcriptions/questions.json"}`. Diagrams, tables,
and math may lose information during text extraction: the agent preserves
available text without solving questions or reconstructing missing visuals.

### Verification

The verifier expects exactly questions 1–36, with nonempty prompts. Questions
34, 35, and 36 have three, two, and four nonempty subquestions respectively;
all other questions have an empty list. A structural failure scores zero.
For structurally valid submissions, 45 reference prose fragments account for
20% of the score, with an equal deduction for each missing fragment. Matching
ignores case, punctuation, and wrapping; the report names affected questions
or subquestions. These spot checks do not establish full transcription accuracy.

Tool checks confirm requested page order and ranges, and that the saved JSON
matches the save input. File checks refuse duplicate JSON keys and symbolic
links in the output path. Saves use a temporary file followed by replacement.

## Layout

```text
├── nanoagent.yaml       # manifest, permissions, tools, and task instructions
├── contract.py          # shared tool/task enums and input/output types
├── pyproject.toml       # package and development dependencies
├── uv.lock              # locked dependencies
├── src/plugin/          # MCP server (__main__.py) and tools (transcribe.py)
│   └── data/            # bundled original exam PDF
├── verifier/            # tool checks, saved-file checks, and exam task scoring
├── tests/               # PDF reads, saves, file validation, MCP, and verifier tests
├── ui/                  # renderer entry point and styles
└── product/             # catalog description and icon
```

## Develop and run

Use Python 3.12 or newer and `uv`. From the plugin root:

```sh
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest
uv run --frozen --extra dev ruff check .
```

Load `nanoagent.yaml` in NanoAgent and run `transcribe-exams` with `{}`.
NanoAgent starts `uv run --frozen python -m plugin` and passes the writable
workspace as `NANOAGENT_WORKSPACE`. Review `transcriptions/questions.json`
in that workspace and the task's verification report.

The tests cover all 28 PDF pages, invalid requests, Unicode saves, repeated and
failed writes, symbolic links, malformed JSON, task scoring, and MCP calls.
The exam-specific question counts and reference fragments live in
`verifier/transcribe.py`; update those if the bundled source exam changes.
