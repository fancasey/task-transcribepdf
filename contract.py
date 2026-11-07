"""NanoAgent contracts for organizing exam questions."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    READ_PDF = "read_pdf"
    SAVE_TRANSCRIPTION = "save_transcription"


class Task(Enum):
    TRANSCRIBE_EXAMS = "transcribe-exams"


SOURCE = "algtwo-82026-exam.pdf"
OUTPUT_PATH = "transcriptions/questions.json"
MAX_PAGES_PER_READ = 5
PAGE_COUNT = 28


@dataclass
class ReadInput(Output):
    pages: Annotated[list[int], "One to five distinct one-based PDF page numbers in reading order"]


@dataclass
class PdfPage(Output):
    page: int
    text: str


@dataclass
class ReadOutput(Output):
    page_count: int
    pages: list[PdfPage]


@dataclass
class Question(Output):
    prompt: Annotated[str, "Question text, shared setup and any multiple-choice options"]
    subquestions: Annotated[list[str], "Separate prompts in printed order, or an empty list"]
    pages: Annotated[list[int], "All one-based PDF pages containing this question, including continuations"]


@dataclass
class SaveInput(Output):
    start_page: int
    end_page: int
    questions: Annotated[dict[str, Question], "Printed question numbers mapped to their question records"]


@dataclass
class SaveOutput(Output):
    path: Annotated[str, "Saved JSON path relative to the workspace"]


@dataclass
class TranscribeInput(Output):
    start_page: Annotated[int, "First one-based PDF page to transcribe"]
    end_page: Annotated[int, "Last page, inclusive; at most five pages per task"]


TOOLS = {
    Tool.READ_PDF: (ReadInput, ReadOutput),
    Tool.SAVE_TRANSCRIPTION: (SaveInput, SaveOutput),
}
TASKS = {Task.TRANSCRIBE_EXAMS: (TranscribeInput, SaveOutput)}


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


# One-based PDF page numbers, independent of submitted provenance.
QUESTION_PAGES = {
    **{str(q): [page] for page, ids in {
        2: range(1, 4), 3: range(4, 7), 4: range(7, 9), 5: range(9, 12),
        6: range(12, 14), 7: range(14, 17), 8: range(17, 19),
        9: range(19, 22), 10: range(22, 25),
        **{page: [page + 14] for page in range(11, 22)},
    }.items() for q in ids},
    "36": [22, 23],
}

