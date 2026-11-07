import pytest

from verifier.transcribe import PROMPT_ANCHORS, QUESTION_PAGES, SUBQUESTION_ANCHORS


@pytest.fixture
def questions():
    return {
        str(number): {"prompt": anchor, "subquestions": list(SUBQUESTION_ANCHORS.get(str(number), ())), "pages": QUESTION_PAGES[str(number)]}
        for number, anchor in enumerate(PROMPT_ANCHORS, 1)
    }
