"""Read the bundled text-layer PDF and save organized questions."""

import json
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile

import pypdfium2 as pdfium
from slimconfig import plain_output

from contract import (
    MAX_PAGES_PER_READ,
    OUTPUT_PATH,
    SOURCE,
    PdfPage,
    ReadInput,
    ReadOutput,
    SaveInput,
    SaveOutput,
    validate_save,
)

SAMPLE = Path(__file__).parent / "data" / SOURCE


def read_pdf(value: ReadInput, workspace: Path) -> ReadOutput:
    pages = value.pages
    if not 1 <= len(pages) <= MAX_PAGES_PER_READ or pages != sorted(set(pages)):
        raise ValueError("Request one to five distinct pages in increasing order")
    with pdfium.PdfDocument(SAMPLE) as pdf:
        if pages[0] < 1 or pages[-1] > len(pdf):
            raise ValueError(f"Page numbers must be between 1 and {len(pdf)}")
        texts = []
        for number in pages:
            with closing(pdf[number - 1]) as page, closing(page.get_textpage()) as text_page:
                texts.append(PdfPage(number, text_page.get_text_bounded().replace("\r\n", "\n")))
        return ReadOutput(len(pdf), texts)


def save_transcription(value: SaveInput, workspace: Path) -> SaveOutput:
    validate_save(value)
    target = workspace.resolve() / OUTPUT_PATH
    if target.resolve() != target:
        raise ValueError("Output path must not contain a symbolic link")
    payload = json.dumps(plain_output(value), ensure_ascii=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as temporary:
        temp_path = Path(temporary.name)
        try:
            temporary.write(payload)
            temporary.close()
            temp_path.replace(target)
        finally:
            temp_path.unlink(missing_ok=True)
    return SaveOutput(OUTPUT_PATH)
