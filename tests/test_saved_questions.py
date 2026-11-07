"""Exercise each independently scored response and each structural requirement."""

import json

import pytest

from contract import OUTPUT_PATH, SaveOutput, TranscribeInput
from verifier import verify_task

IDS = [str(number) for number in range(1, 37)]
PARTS = [(key, index) for key, count in (("34", 3), ("35", 2), ("36", 4)) for index in range(count)]
RESPONSES = [(key, None) for key in IDS] + PARTS


def verdict(tmp_path, payload):
    target = tmp_path / OUTPUT_PATH
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return verify_task("transcribe-exams", TranscribeInput(), SaveOutput(OUTPUT_PATH), None, tmp_path)


@pytest.mark.parametrize("key", IDS)
def test_each_question_is_required(tmp_path, questions, key):
    del questions[key]
    found = verdict(tmp_path, {"questions": questions})
    assert found["valid"] is False
    assert found["score"] == 0
    assert found["details"]["missing"] == [key]


@pytest.mark.parametrize("key,index", RESPONSES)
def test_each_phrase_has_equal_weight_and_precise_diagnostic(tmp_path, questions, key, index):
    if index is None:
        questions[key]["prompt"] = "Unrelated prose"
    else:
        questions[key]["subquestions"][index] = "Unrelated prose"
    found = verdict(tmp_path, {"questions": questions})
    assert found["valid"] is True
    assert found["score"] == pytest.approx(1 - 0.2 / 45)
    assert found["details"]["text_warnings"] == [key if index is None else f"{key}.{index + 1}"]


@pytest.mark.parametrize("key,index", RESPONSES)
def test_each_phrase_tolerates_case_punctuation_and_wrapping(tmp_path, questions, key, index):
    record = questions[key]
    text = record["prompt"] if index is None else record["subquestions"][index]
    text = "Context before. " + " —\n".join(text.upper().replace("'", "’").split()) + ". Context after."
    if index is None:
        record["prompt"] = text
    else:
        record["subquestions"][index] = text
    found = verdict(tmp_path, {"questions": questions})
    assert found["valid"] is True
    assert found["score"] == 1
    assert found["details"]["text_warnings"] == []


@pytest.mark.parametrize("key", IDS)
@pytest.mark.parametrize("field,value", [("prompt", " \n\t"), ("subquestions", None)])
def test_malformed_record_is_identified_for_every_question(tmp_path, questions, key, field, value):
    questions[key][field] = value
    found = verdict(tmp_path, {"questions": questions})
    assert found["valid"] is False
    assert found["score"] == 0
    assert found["details"]["invalid"] == [key]


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        0,
        [],
        "text",
        {},
        {"prompt": "text"},
        {"prompt": 3, "subquestions": []},
        {"prompt": "text", "subquestions": [None]},
        {"prompt": "text", "subquestions": [" "]},
    ],
)
def test_wrong_record_types_return_verdicts(tmp_path, questions, value):
    questions["1"] = value
    found = verdict(tmp_path, {"questions": questions})
    assert found["score"] == 0
    assert found["details"]["invalid"] == ["1"]


@pytest.mark.parametrize("key", IDS)
def test_extra_response_is_a_structural_failure(tmp_path, questions, key):
    expected = len(questions[key]["subquestions"])
    questions[key]["subquestions"].append("Extra response")
    found = verdict(tmp_path, {"questions": questions})
    assert found["score"] == 0
    assert found["details"]["subquestion_counts"] == {key: {"expected": expected, "actual": expected + 1}}


@pytest.mark.parametrize("key,index", PARTS)
def test_each_subquestion_is_required(tmp_path, questions, key, index):
    expected = len(questions[key]["subquestions"])
    questions[key]["subquestions"].pop(index)
    found = verdict(tmp_path, {"questions": questions})
    assert found["score"] == 0
    assert found["details"]["subquestion_counts"] == {key: {"expected": expected, "actual": expected - 1}}


@pytest.mark.parametrize("payload", [None, [], 0, "text", {}, {"questions": None}, {"questions": []}])
def test_wrong_document_shape_is_rejected(tmp_path, payload):
    found = verdict(tmp_path, payload)
    assert found["valid"] is False
    assert found["score"] == 0


@pytest.mark.parametrize("key", ["0", "01", "37", "-1", "１", "a", "", "1.0"])
def test_unexpected_ids_are_reported(tmp_path, questions, key):
    questions[key] = {"prompt": "text", "subquestions": []}
    found = verdict(tmp_path, {"questions": questions})
    assert found["score"] == 0
    assert found["details"]["unexpected"] == [key]
