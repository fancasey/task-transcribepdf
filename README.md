# Organize Exam Questions

This NanoAgent task reads the original August 2026 New York Algebra II Regents
exam. PDFium extracts the embedded text locally. The agent organizes the
questions into JSON, with a list for the distinct prompts inside each multipart
question. The workflow uses a text-only model.

## Run

Run `transcribe-exams` with `{}`. The task reads
[the bundled exam](src/plugin/data/algtwo-82026-exam.pdf) and returns
`transcriptions/questions.json` in the run workspace.

```json
{
  "questions": {
    "1": {"prompt": "Question text and answer choices", "subquestions": []},
    "34": {"prompt": "Shared setup", "subquestions": ["First prompt", "Second prompt", "Third prompt"]}
  }
}
```

The verifier expects questions 1–36. Questions 34, 35, and 36 have three, two,
and four subquestions respectively. Multiple-choice options and instructions
that qualify a single response stay in the main prompt.

The verifier requires the correct IDs and counts, with nonempty text in every
prompt. For structurally valid submissions, the 45 reference phrases are
worth 20% of the score in total, with an equal deduction for each missing
phrase. The report identifies the affected questions or subquestions.
The phrase check ignores case, punctuation, and wrapping and focuses on prose.

## Develop

```sh
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest
```
