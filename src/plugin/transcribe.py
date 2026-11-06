"""Read bundled exam pages and save structured transcriptions."""

import base64
import json
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

import pypdfium2 as pdfium

from contract import (
    DOCUMENT_TYPES,
    MAX_PAGES_PER_READ,
    OUTPUT_FOLDER,
    STUDENT_IDS,
    SUBJECTS,
    DocumentInput,
    PageImage,
    PdfPage,
    ReadInput,
    ReadOutput,
    SaveInput,
    SaveOutput,
)

DATA = Path(__file__).parent / "data"


def _document(value: DocumentInput) -> tuple[Path, Path]:
    if value.subject not in SUBJECTS or value.document_type not in DOCUMENT_TYPES:
        raise ValueError("Choose ela or alg2 and a supported document type")
    folder = Path(value.subject)
    if value.document_type == "student_response":
        if value.student_id not in STUDENT_IDS[value.subject]:
            raise ValueError(f"Unknown student ID for {value.subject}")
        source = folder / SUBJECTS[value.subject] / f"{value.student_id}.pdf"
        output = folder / "students" / f"{value.student_id}.json"
    else:
        if value.student_id is not None:
            raise ValueError("Only student responses take a student ID")
        source = folder / f"{value.document_type}.pdf"
        output = source.with_suffix(".json")
    return DATA / source, Path(OUTPUT_FOLDER) / output


def read_pdf(value: ReadInput, workspace: Path) -> ReadOutput:
    source, _ = _document(value)
    pages = value.pages
    with pdfium.PdfDocument(source) as pdf:
        if not 1 <= len(pages) <= MAX_PAGES_PER_READ or pages != sorted(set(pages)):
            raise ValueError("Request one to three distinct pages in increasing order")
        if pages[0] < 1 or pages[-1] > len(pdf):
            raise ValueError(f"Page numbers must be between 1 and {len(pdf)}")
        texts = []
        images = []
        for number in pages:
            page = pdf[number - 1]
            text_page = page.get_textpage()
            bitmap = page.render(scale=1700 / max(page.get_size()))
            try:
                with BytesIO() as stream:
                    bitmap.to_pil().save(stream, format="PNG")
                    images.append(PageImage("image/png", base64.b64encode(stream.getvalue()).decode("ascii")))
                texts.append(PdfPage(number, text_page.get_text_bounded().replace("\r\n", "\n")))
            finally:
                bitmap.close()
                text_page.close()
                page.close()
        return ReadOutput(len(pdf), texts, images)


def save_transcription(value: SaveInput, workspace: Path) -> SaveOutput:
    source, relative = _document(value)
    if any(not key.isdecimal() or not isinstance(record, dict) for key, record in value.questions.items()):
        raise ValueError("questions must map numeric question IDs to objects")
    workspace = workspace.resolve()
    target = workspace / relative
    if target.resolve() != target:
        raise ValueError("Output path must not contain a symbolic link")
    with pdfium.PdfDocument(source) as pdf:
        document = {
            "document_type": value.document_type,
            "source": f"../{source.name}",
            "page_count": len(pdf),
            "questions": value.questions,
            "supplementary_info": value.supplementary_info,
        }
    if value.student_id is not None:
        document["student_id"] = value.student_id
    payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as temporary:
        temp_path = Path(temporary.name)
        try:
            temporary.write(payload)
            temporary.close()
            temp_path.replace(target)
        finally:
            temp_path.unlink(missing_ok=True)
    return SaveOutput(relative.as_posix())
