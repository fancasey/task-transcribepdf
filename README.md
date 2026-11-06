# Exam PDF Transcription

This NanoAgent plugin converts the bundled ELA and Algebra II Regents excerpts,
rating guides, and selected student responses into JSON. It transcribes source
material and organizes it for a downstream grader.

## Exam sources

The bundled exam excerpts come from the New York State Education Department's
August 2026 Regents examinations.

- English Language Arts ([official exam PDF](https://www.nysedregents.org/hsela/826/reela-82026-exam.pdf), [NYSED exam archive](https://www.nysedregents.org/hsela/))
- Algebra II ([official exam PDF](https://www.nysedregents.org/algebratwo/826/algtwo-82026-exam.pdf), [NYSED exam archive](https://www.nysedregents.org/algebratwo/))

## Run

Use the `transcribe-exams` agent task with both selection lists. An empty list
skips that subject. ELA IDs are `92` through `99` and Algebra II IDs are `1` through `6`.

```json
{"ela_students": ["92"], "math_students": ["1", "3"]}
```

The Algebra II packet omits question 28 and retains the original numbering for the other questions.

The agent saves `transcriptions/<subject>/questions.json`,
`transcriptions/<subject>/rubric.json`, and
`transcriptions/<subject>/students/<id>.json` for each requested student. The
subject directories are `ela` and `alg2`. The task output lists those files
relative to the run workspace.

Use a NanoAgent provider and model that accept images in tool results. The
local NanoAgent checkout supports this through its Bedrock backend. PDF
rendering and verification run locally without their own credentials. The
runner still needs credentials for the chosen model. For larger selections,
allow sufficient model steps, context, and output tokens to read and transcribe
the full packet.

## Tools

Both tools identify a bundled PDF by `subject` (`ela` or `alg2`),
`document_type` (`questions`, `rubric`, or `student_response`), and `student_id`.
Use a student ID for `student_response` and `null` for the other document types.

| Tool | Additional inputs | Result |
| --- | --- | --- |
| `read_pdf` | `pages`, a list of one to three distinct, one-based page numbers in increasing order | Returns the PDF's total page count, embedded text labeled by page number, and a matching PNG image for each requested page. |
| `save_transcription` | `questions`, an object keyed by numeric question ID, and `supplementary_info` for shared material such as directions or scoring guidance | Saves one JSON file at a fixed path for the document, adds source metadata and page count, and returns the workspace-relative path. |

### Tasks

| Task | Runner and tools | Inputs | Workflow and output |
| --- | --- | --- | --- |
| `transcribe-exams` | `agent` using `read_pdf` and `save_transcription` | `ela_students` (string IDs `92`–`99`) and `math_students` (string IDs `1`–`6`). An empty list skips that subject. | For each selected subject, reads every page of the questions, rubric, and selected student PDFs in batches. Saves one transcription per PDF and returns `folder` (`transcriptions`) and `files` (the exact saved paths relative to the workspace). |

## Layout

- `src/plugin/data/` contains the bundled PDFs and reference JSON.
- `src/plugin/transcribe.py` renders pages and saves transcriptions.
- `verifier/` checks the tool results and scores the saved packet.

## Verification

The deterministic verifier reads the saved files and compares them to the
bundled references. Reference contents are unavailable through the agent tools.

- An organization issue generally costs **10** points. A missing or unreadable
  file costs **100**. Checks cover question IDs, counts, subitems, response
  page segments, rubric score keys, and page placement. A missing subtree
  receives a structural penalty without also counting its missing words.
- An ordinary token edit costs **0.25** points. Numeric and mathematical token
  edits and exact numeric value changes cost **0.75**. Whitespace between tokens,
  typographic quotes, Unicode minus signs, multiplication and division glyphs,
  and common forms of simple superscripts are normalized. Word boundaries and
  token order are preserved.
- The score is `max(0, 1 - total_penalty / (100 * expected_files))`. A run is
  structurally valid when it has no organization penalties. See the separate
  penalty subtotals and issue locations in the verdict.
- Student text marked as OCR or unrecognized in the references is advisory
  only. Manually transcribed segments count toward accuracy. The current
  student references group work by question and page, so the verifier cannot
  independently check assignments between response slots on the same page.
  Diagrams remain available in the source images. Free-form visual notes are
  saved but do not affect the score.

## Develop and run

```sh
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest
```
