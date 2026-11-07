import pytest
from test_saved_questions import subset, verdict


@pytest.mark.parametrize("field,value", [("prompt", ""), ("subquestions", None), ("pages", [3])])
def test_invalid_record(tmp_path, questions, field, value):
    selected = subset(questions, 1, 5)
    selected["1"][field] = value
    assert verdict(tmp_path, selected, 1, 5)["details"]["invalid"] == ["1"]


def test_multipart_counts_are_checked_in_selected_interval(tmp_path, questions):
    selected = subset(questions, 19, 23)
    selected["36"]["subquestions"].pop()
    found = verdict(tmp_path, selected, 19, 23)
    assert not found["valid"]
    assert found["details"]["subquestion_counts"] == {"36": {"expected": 4, "actual": 3}}
