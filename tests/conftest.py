import pytest

from verifier.transcribe import PROMPT_ANCHORS, SUBQUESTION_ANCHORS


@pytest.fixture
def questions():
    return {
        str(number): {"prompt": anchor, "subquestions": list(SUBQUESTION_ANCHORS.get(str(number), ()))}
        for number, anchor in enumerate(PROMPT_ANCHORS, 1)
    }
