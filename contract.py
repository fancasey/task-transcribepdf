"""NanoAgent tool and task contracts for exam transcription."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any

from slimconfig import Output


class Tool(Enum):
    READ_PDF = "read_pdf"
    SAVE_TRANSCRIPTION = "save_transcription"


class Task(Enum):
    TRANSCRIBE_EXAMS = "transcribe-exams"


SUBJECTS = {"ela": "student_responses", "alg2": "students"}
STUDENT_IDS = {"ela": ("92", "93", "94", "95", "96", "97", "98", "99"), "alg2": ("1", "2", "3", "4", "5", "6")}
DOCUMENT_TYPES = ("questions", "rubric", "student_response")
OUTPUT_FOLDER = "transcriptions"
MAX_PAGES_PER_READ = 3


@dataclass
class DocumentInput(Output):
    subject: Annotated[str, "ela or alg2 (math)"]
    document_type: Annotated[str, "questions, rubric, or student_response"]
    student_id: Annotated[str | None, "Student ID for student_response only"]


@dataclass
class ReadInput(DocumentInput):
    pages: Annotated[list[int], "One to three distinct one-based PDF page numbers in reading order"]


@dataclass
class PdfPage(Output):
    page: int
    text: str


@dataclass
class PageImage(Output):
    media_type: str
    data: str


@dataclass
class ReadOutput(Output):
    page_count: int
    pages: list[PdfPage]
    images: list[PageImage]


@dataclass
class SaveInput(DocumentInput):
    questions: Annotated[dict[str, Any], "Question IDs mapped to structured transcription records"]
    supplementary_info: Annotated[dict[str, Any], "Shared directions, scoring guidance and headings"]


@dataclass
class SaveOutput(Output):
    path: Annotated[str, "Saved JSON path relative to the workspace"]


@dataclass
class TranscribeInput(Output):
    ela_students: Annotated[list[str], "ELA IDs 92–99. Use an empty list to skip ELA."]
    math_students: Annotated[list[str], "Algebra II IDs 1–6. Use an empty list to skip math."]


@dataclass
class TranscribeOutput(Output):
    folder: str
    files: Annotated[list[str], "Paths returned by save_transcription for this request"]


TOOLS = {
    Tool.READ_PDF: (ReadInput, ReadOutput),
    Tool.SAVE_TRANSCRIPTION: (SaveInput, SaveOutput),
}
TASKS = {Task.TRANSCRIBE_EXAMS: (TranscribeInput, TranscribeOutput)}
