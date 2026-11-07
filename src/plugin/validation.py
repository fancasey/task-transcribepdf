"""Runtime checks for tool inputs."""

from contract import MAX_PAGES_PER_READ, PAGE_COUNT, QUESTION_PAGES


def validate_interval(start, end):
    if not 1 <= start <= end <= PAGE_COUNT or end - start + 1 > MAX_PAGES_PER_READ:
        raise ValueError("Select a contiguous interval of one to five pages between 1 and 28")


def validate_save(value):
    validate_interval(value.start_page, value.end_page)
    if any(not key.isascii() or not key.isdecimal() for key in value.questions):
        raise ValueError("questions must map numeric question IDs to question records")
    for key, question in value.questions.items():
        if key not in QUESTION_PAGES or question.pages != QUESTION_PAGES[key]:
            raise ValueError("Question pages must match the complete source question")
        if (not question.pages or question.pages != sorted(set(question.pages))
                or any(page < value.start_page or page > value.end_page for page in question.pages)):
            raise ValueError("Question pages must be distinct, ordered, and inside the selected interval")
