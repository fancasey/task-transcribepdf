import asyncio
import base64
import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from contract import ReadInput, SaveInput, TranscribeInput, TranscribeOutput
from plugin.transcribe import read_pdf, save_transcription
from verifier import verify_input, verify_output, verify_task
from verifier.transcribe import compare, packet_documents


def test_mcp_returns_tool_images_and_embedded_text(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOAGENT_WORKSPACE", str(tmp_path))

    async def call():
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "plugin"], env={"NANOAGENT_WORKSPACE": str(tmp_path)}
        )
        async with stdio_client(parameters) as (reader, writer), ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool(
                "read_pdf", {"subject": "alg2", "document_type": "questions", "student_id": None, "pages": [1, 2]}
            )
            assert not result.isError
            data = result.structuredContent
            assert data["page_count"] == 12
            assert [page["page"] for page in data["pages"]] == [1, 2]
            assert "observational study" in data["pages"][0]["text"]
            assert len(data["images"]) == 2
            for image in data["images"]:
                assert image["media_type"] == "image/png"
                assert base64.b64decode(image["data"]).startswith(b"\x89PNG\r\n\x1a\n")

    asyncio.run(call())


def test_reader_rejects_bad_pages_and_student_ids(tmp_path):
    with pytest.raises(ValueError, match="Unknown student"):
        read_pdf(ReadInput("ela", "student_response", "../92", [1]), tmp_path)
    with pytest.raises(ValueError, match="between"):
        read_pdf(ReadInput("ela", "rubric", None, [2]), tmp_path)


@pytest.mark.parametrize(
    "pages",
    [[], [0], [-1], [1, 1], [2, 1], [1, 2, 3, 4]],
    ids=["empty", "zero", "negative", "duplicate", "reversed", "above-batch-limit"],
)
def test_invalid_page_batches_fail_input_check_and_reader(tmp_path, pages):
    request = ReadInput("alg2", "questions", None, pages)
    verdict = verify_input("read_pdf", request)
    assert verdict["valid"] is False
    assert verdict["score"] == 0
    with pytest.raises(ValueError, match="distinct pages|Page numbers must be between"):
        read_pdf(request, tmp_path)


@pytest.mark.parametrize("pages", [[1], [12], [1, 7, 12]], ids=["first", "last", "batch-limit"])
def test_valid_page_boundaries_round_trip(tmp_path, pages):
    request = ReadInput("alg2", "questions", None, pages)
    assert verify_input("read_pdf", request)["valid"] is True
    output = read_pdf(request, tmp_path)
    assert output.page_count == 12
    assert [page.page for page in output.pages] == pages
    assert len(output.images) == len(pages)
    assert verify_output("read_pdf", request, output, tmp_path)["score"] == 1


@pytest.mark.parametrize("change", ["order", "missing-image", "page-count", "media-type", "image-data"])
def test_wrong_pdf_tool_output_is_rejected(tmp_path, change):
    request = ReadInput("alg2", "questions", None, [1, 12])
    output = read_pdf(request, tmp_path)
    if change == "order":
        output.pages.reverse()
    elif change == "missing-image":
        output.images.pop()
    elif change == "page-count":
        output.page_count = 11
    elif change == "media-type":
        output.images[0].media_type = "image/jpeg"
    else:
        output.images[0].data = "not a PNG"
    verdict = verify_output("read_pdf", request, output, tmp_path)
    assert verdict["valid"] is False
    assert verdict["score"] == 0
    assert verdict["message"] == "PDF page output differs from request"


def test_save_verifier_checks_on_disk_content(tmp_path):
    request = SaveInput("alg2", "student_response", "1", {"25": {"text": "x = 2"}}, {})
    output = save_transcription(request, tmp_path)
    assert verify_output("save_transcription", request, output, tmp_path)["score"] == 1
    path = tmp_path / output.path
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["questions"]["25"]["text"] = "x = 3"
    path.write_text(json.dumps(saved), encoding="utf-8")
    verdict = verify_output("save_transcription", request, output, tmp_path)
    assert verdict["valid"] is False
    assert verdict["score"] == 0
    assert verdict["message"] == "Saved transcription differs from tool input"


def save_reference_packet(tmp_path, selections):
    files = []
    for relative, reference_path in packet_documents(selections):
        reference = json.loads(reference_path.read_text())
        value = SaveInput(
            relative.parts[1],
            reference["document_type"],
            reference.get("student_id"),
            reference["questions"],
            reference["supplementary_info"],
        )
        files.append(save_transcription(value, tmp_path).path)
    return TranscribeOutput("transcriptions", files)


def test_both_subjects_score_and_missing_subitem_penalty(tmp_path):
    arguments = TranscribeInput(["92"], ["1"])
    output = save_reference_packet(tmp_path, arguments)
    verdict = verify_task("transcribe-exams", arguments, output, None, tmp_path)
    assert verdict["valid"] and verdict["score"] == 1
    assert verdict["details"]["ocr_advisory_segments"] == 0
    questions_path = tmp_path / "transcriptions/alg2/questions.json"
    questions = json.loads(questions_path.read_text())
    questions["questions"]["36"]["subitems"].pop(1)
    questions_path.write_text(json.dumps(questions))
    verdict = verify_task("transcribe-exams", arguments, output, None, tmp_path)
    assert not verdict["valid"]
    assert verdict["details"]["organization_penalty"] == 10
    assert verdict["details"]["transcription_penalty"] == 0


def test_scores_math_and_detects_rubric_columns_swapped():
    findings = []
    compare("x² − 2 × 3", "x^{ 2 }  -\n2 * 3", "answer", findings)
    assert findings == []
    compare("x² − 2", "x^2 + 2", "answer", findings)
    assert findings[0][:2] == ("transcription", 0.75)
    findings.clear()
    compare(
        {"2": "Complete", "1": "Partial"}, {"1": "Complete", "2": "Partial"}, "rubric", findings, "score_descriptors"
    )
    assert [issue[:2] for issue in findings] == [("organization", 10), ("organization", 10)]


def test_ocr_differences_are_advisory_but_wrong_page_is_structural():
    findings = []
    compare(
        {"source_page": 2, "text": "784", "transcription_method": "ocr"},
        {"source_page": 3, "text": "184"},
        "response",
        findings,
    )
    assert [issue[:2] for issue in findings] == [("organization", 10), ("ocr_advisory", 0.75)]


def test_rejects_extra_files_and_unsafe_output(tmp_path):
    arguments = TranscribeInput([], ["1"])
    output = save_reference_packet(tmp_path, arguments)
    unexpected = tmp_path / "transcriptions/alg2/students/2.json"
    unexpected.write_text("{}")
    verdict = verify_task("transcribe-exams", arguments, output, None, tmp_path)
    assert verdict["details"]["organization_penalty"] == 10
    target = tmp_path / output.files[0]
    target.unlink()
    target.symlink_to(unexpected)
    with pytest.raises(ValueError, match="symbolic link"):
        save_transcription(SaveInput("alg2", "questions", None, {}, {}), tmp_path)
