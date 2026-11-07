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
MAX_PAGES_PER_READ = 3


@dataclass
class ReadInput(Output):
    pages: Annotated[list[int], "One to three distinct one-based PDF page numbers in reading order"]


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


@dataclass
class SaveInput(Output):
    questions: Annotated[dict[str, Question], "Printed question numbers mapped to their question records"]


@dataclass
class SaveOutput(Output):
    path: Annotated[str, "Saved JSON path relative to the workspace"]


@dataclass
class TranscribeInput(Output):
    pass


TOOLS = {
    Tool.READ_PDF: (ReadInput, ReadOutput),
    Tool.SAVE_TRANSCRIPTION: (SaveInput, SaveOutput),
}
TASKS = {Task.TRANSCRIBE_EXAMS: (TranscribeInput, SaveOutput)}
