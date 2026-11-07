import json

import pytest

from contract import OUTPUT_PATH, SaveOutput, TranscribeInput
from verifier import verify_task


def verify(workspace, questions):
    target = workspace / OUTPUT_PATH
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps({"questions": questions}), encoding="utf-8")
    return verify_task("transcribe-exams", TranscribeInput(), SaveOutput(OUTPUT_PATH), None, workspace)


def test_task_accepts_structure_and_ignores_text_formatting(tmp_path, questions):
    questions["35"]["subquestions"][1] = "SUPPORT THE\nSUPERINTENDENT’S CONCERN?"
    verdict = verify(tmp_path, questions)
    assert verdict["score"] == 1
    assert verdict["details"]["text_warnings"] == []


def test_task_deducts_for_misplaced_text_without_failing_structure(tmp_path, questions):
    parts = questions["36"]["subquestions"]
    parts[0], parts[1] = parts[1], parts[0]
    verdict = verify(tmp_path, questions)
    assert verdict["valid"]
    assert verdict["score"] == pytest.approx(1 - 0.20 * 2 / 45)
    assert verdict["details"]["text_warnings"] == ["36.1", "36.2"]


def test_task_deducts_for_one_missing_prompt_phrase(tmp_path, questions):
    questions["7"]["prompt"] = "Review the work shown."
    verdict = verify(tmp_path, questions)
    assert verdict["valid"]
    assert verdict["score"] == pytest.approx(1 - 0.20 / 45)
    assert verdict["details"]["text_warnings"] == ["7"]


def test_task_caps_text_deductions_at_twenty_percent(tmp_path, questions):
    for question in questions.values():
        question["prompt"] = "Unrelated text."
        question["subquestions"] = ["Unrelated text."] * len(question["subquestions"])
    verdict = verify(tmp_path, questions)
    assert verdict["valid"]
    assert verdict["score"] == pytest.approx(0.80)
    assert len(verdict["details"]["text_warnings"]) == 45


def test_task_checks_exact_ids_and_subquestion_counts(tmp_path, questions):
    questions["37"] = questions.pop("28")
    questions["36"]["subquestions"].pop()
    questions["1"]["subquestions"].append("A multiple-choice option")
    verdict = verify(tmp_path, questions)
    assert verdict["score"] == 0
    assert verdict["details"]["missing"] == ["28"]
    assert verdict["details"]["unexpected"] == ["37"]
    assert verdict["details"]["subquestion_counts"] == {
        "1": {"expected": 0, "actual": 1},
        "36": {"expected": 4, "actual": 3},
    }


def test_task_rejects_missing_file(tmp_path):
    verdict = verify_task("transcribe-exams", TranscribeInput(), SaveOutput(OUTPUT_PATH), None, tmp_path)
    assert verdict["score"] == 0
