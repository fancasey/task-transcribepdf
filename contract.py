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
    transcription: Annotated[SaveInput, "Complete transcription, identical to the saved JSON"]


@dataclass
class TranscribeInput(Output):
    start_page: Annotated[int, "First one-based PDF page to transcribe"]
    end_page: Annotated[int, "Last page, inclusive; at most five pages per task"]


TOOLS = {
    Tool.READ_PDF: (ReadInput, ReadOutput),
    Tool.SAVE_TRANSCRIPTION: (SaveInput, SaveOutput),
}
TASKS = {Task.TRANSCRIBE_EXAMS: (TranscribeInput, SaveOutput)}


# One-based PDF page numbers, independent of submitted provenance.
QUESTION_PAGES = {
    "1": [2],
    "2": [2],
    "3": [2],
    "4": [3],
    "5": [3],
    "6": [3],
    "7": [4],
    "8": [4],
    "9": [5],
    "10": [5],
    "11": [5],
    "12": [6],
    "13": [6],
    "14": [7],
    "15": [7],
    "16": [7],
    "17": [8],
    "18": [8],
    "19": [9],
    "20": [9],
    "21": [9],
    "22": [10],
    "23": [10],
    "24": [10],
    "25": [11],
    "26": [12],
    "27": [13],
    "28": [14],
    "29": [15],
    "30": [16],
    "31": [17],
    "32": [18],
    "33": [19],
    "34": [20],
    "35": [21],
    "36": [22, 23],
}
