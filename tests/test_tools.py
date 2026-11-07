"""Real PDF reads, durable saves, and boundary verification."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from slimconfig import plain_output

from contract import OUTPUT_PATH, PdfPage, Question, ReadInput, ReadOutput, SaveInput
from plugin.transcribe import read_pdf, save_transcription
from verifier import verify_input, verify_output


@pytest.mark.parametrize("number", range(1, 29))
def test_every_pdf_page_can_be_read(number, tmp_path):
    output = read_pdf(ReadInput([number]), tmp_path)
    assert output.page_count == 28
    assert [page.page for page in output.pages] == [number]
    assert isinstance(output.pages[0].text, str)
    # The bundled exam has one page with no embedded text.
    if number == 24:
        assert output.pages[0].text == ""
    else:
        assert output.pages[0].text.strip()
    assert "\r\n" not in output.pages[0].text
    assert verify_output("read_pdf", ReadInput([number]), output, tmp_path)["valid"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("pages", [[1], [1, 2], [1, 14, 28], [26, 27, 28]])
def test_valid_batches_preserve_individual_page_text(pages, tmp_path):
    request = ReadInput(pages)
    assert verify_input("read_pdf", request)["valid"]
    batch = read_pdf(request, tmp_path)
    assert [plain_output(page) for page in batch.pages] == [
        plain_output(read_pdf(ReadInput([number]), tmp_path).pages[0]) for number in pages
    ]


@pytest.mark.parametrize("pages", [[], [0], [-1], [1, 1], [2, 1], [1, 2, 3, 4]])
def test_input_verifier_rejects_bad_page_requests(pages):
    found = verify_input("read_pdf", ReadInput(pages))
    assert found["valid"] is False
    assert found["score"] == 0


@pytest.mark.parametrize("numbers,count", [([], 28), ([2], 28), ([1, 2], 28), ([1], 0)])
def test_output_verifier_rejects_missing_extra_wrong_or_out_of_range_pages(tmp_path, numbers, count):
    output = ReadOutput(count, [PdfPage(number, "text") for number in numbers])
    assert not verify_output("read_pdf", ReadInput([1]), output, tmp_path)["valid"]


@pytest.fixture
def submission():
    return SaveInput({"1": Question("π ≥ 2 — café\nSecond line", []), "34": Question("Shared", ["Part one"])})


def test_save_creates_nested_workspace_and_round_trips_unicode(tmp_path, submission):
    workspace = tmp_path / "new" / "workspace"
    output = save_transcription(submission, workspace)
    assert output.path == OUTPUT_PATH
    target = workspace / output.path
    assert json.loads(target.read_text()) == plain_output(submission)
    assert "π" in target.read_text()
    assert target.read_text().endswith("\n")
    assert list(target.parent.iterdir()) == [target]
    assert verify_output("save_transcription", submission, output, workspace)["valid"]


def test_second_save_replaces_previous_content(tmp_path, submission):
    save_transcription(submission, tmp_path)
    submission.questions.pop("34")
    save_transcription(submission, tmp_path)
    assert json.loads((tmp_path / OUTPUT_PATH).read_text()) == plain_output(submission)


@pytest.mark.parametrize("key", ["", "a", "../1", "1.0", "-1", "１", "١", "²", " 1"])
def test_save_and_input_verifier_reject_non_ascii_decimal_ids(tmp_path, key):
    value = SaveInput({key: Question("Text", [])})
    assert not verify_input("save_transcription", value)["valid"]
    with pytest.raises(ValueError, match="numeric question IDs"):
        save_transcription(value, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_empty_submission_is_rejected(tmp_path):
    value = SaveInput({})
    assert not verify_input("save_transcription", value)["valid"]
    with pytest.raises(ValueError):
        save_transcription(value, tmp_path)


@pytest.mark.parametrize("link_parent", [False, True])
def test_save_refuses_symlinks_without_modifying_destination(tmp_path, submission, link_parent):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "questions.json"
    protected.write_text("untouched")
    if link_parent:
        (workspace / "transcriptions").symlink_to(outside, target_is_directory=True)
    else:
        (workspace / "transcriptions").mkdir()
        (workspace / OUTPUT_PATH).symlink_to(protected)
    with pytest.raises(ValueError, match="symbolic link"):
        save_transcription(submission, workspace)
    assert protected.read_text() == "untouched"


def test_failed_replacement_preserves_previous_save_and_cleans_temporary_file(tmp_path, submission):
    save_transcription(submission, tmp_path)
    target = tmp_path / OUTPUT_PATH
    original = target.read_bytes()
    submission.questions["1"].prompt = "Changed"
    with (
        patch.object(Path, "replace", side_effect=OSError("disk failure")),
        pytest.raises(OSError, match="disk failure"),
    ):
        save_transcription(submission, tmp_path)
    assert target.read_bytes() == original
    assert list(target.parent.iterdir()) == [target]


def test_output_verifier_detects_saved_content_changes(tmp_path, submission):
    output = save_transcription(submission, tmp_path)
    submission.questions["1"].prompt = "Different"
    assert not verify_output("save_transcription", submission, output, tmp_path)["valid"]
