"""Interval scoring uses independent source provenance, including cut-off questions."""
import json

import pytest

from contract import OUTPUT_PATH, SaveOutput, TranscribeInput
from verifier import verify_task
from verifier.transcribe import QUESTION_PAGES


def verdict(tmp_path, questions, start, end):
    target = tmp_path / OUTPUT_PATH
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps({"start_page": start, "end_page": end, "questions": questions}))
    return verify_task("transcribe-exams", TranscribeInput(start, end), SaveOutput(OUTPUT_PATH), None, tmp_path)


def subset(questions, start, end):
    return {key: value for key, value in questions.items()
            if all(start <= p <= end for p in QUESTION_PAGES[key])}


@pytest.mark.parametrize("start", range(1, 29))
def test_every_five_page_interval(tmp_path, questions, start):
    end = min(start + 4, 28)
    selected = subset(questions, start, end)
    assert verdict(tmp_path, selected, start, end)["score"] == 1
    for key in list(selected):
        incomplete = dict(selected)
        del incomplete[key]
        found = verdict(tmp_path, incomplete, start, end)
        assert not found["valid"]
        assert found["details"]["missing"] == [key]


@pytest.mark.parametrize("start,end", [(18, 22), (23, 27)])
def test_cut_off_question_is_excluded_and_cannot_fake_provenance(tmp_path, questions, start, end):
    selected = subset(questions, start, end)
    assert "36" not in selected
    assert verdict(tmp_path, selected, start, end)["score"] == 1
    selected["36"] = questions["36"]
    selected["36"]["pages"] = [start]
    assert verdict(tmp_path, selected, start, end)["details"]["unexpected"] == ["36"]


def test_complete_continuation_is_required(tmp_path, questions):
    assert verdict(tmp_path, subset(questions, 21, 25), 21, 25)["score"] == 1
    selected = subset(questions, 21, 25)
    selected["36"]["pages"] = [22]
    assert verdict(tmp_path, selected, 21, 25)["details"]["invalid"] == ["36"]


@pytest.mark.parametrize("start,end", [(1, 6), (0, 4), (5, 4), (25, 29)])
def test_invalid_task_intervals(tmp_path, start, end):
    assert not verdict(tmp_path, {}, start, end)["valid"]


def test_text_scoring_only_counts_selected_questions(tmp_path, questions):
    selected = subset(questions, 1, 5)
    selected["1"]["prompt"] = "Unrelated"
    found = verdict(tmp_path, selected, 1, 5)
    assert found["valid"]
    assert found["score"] == pytest.approx(1 - .2 / 11)
    assert found["details"]["text_warnings"] == ["1"]
