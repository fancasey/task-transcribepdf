import pytest

from contract import OUTPUT_PATH, SaveInput, SaveOutput, TranscribeInput
from verifier import verify_output, verify_task
from verifier.checks import load_saved


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{",
        b"null trailing",
        b' {"questions":{},"questions":{}}',
        b'{"questions":{"1":{"prompt":"a","prompt":"b"}}}',
        b"\xff",
    ],
)
def test_corrupt_or_duplicate_json_is_refused_by_both_verifiers(tmp_path, raw):
    target = tmp_path / OUTPUT_PATH
    target.parent.mkdir()
    target.write_bytes(raw)
    with pytest.raises(ValueError):
        load_saved(tmp_path, OUTPUT_PATH)
    for found in (
        verify_output("save_transcription", SaveInput({}), SaveOutput(OUTPUT_PATH), tmp_path),
        verify_task("transcribe-exams", TranscribeInput(), SaveOutput(OUTPUT_PATH), None, tmp_path),
    ):
        assert found["valid"] is False
        assert found["score"] == 0


@pytest.mark.parametrize("path", ["elsewhere.json", "../questions.json", "/tmp/questions.json", ""])
def test_wrong_output_paths_are_rejected(tmp_path, path):
    assert not verify_output("save_transcription", SaveInput({}), SaveOutput(path), tmp_path)["valid"]
    assert not verify_task("transcribe-exams", TranscribeInput(), SaveOutput(path), None, tmp_path)["valid"]


def test_reader_and_verifiers_refuse_symlinked_saved_file(tmp_path):
    outside = tmp_path / "other.json"
    outside.write_text('{"questions":{}}')
    target = tmp_path / OUTPUT_PATH
    target.parent.mkdir()
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="Unsafe path"):
        load_saved(tmp_path, OUTPUT_PATH)
    assert not verify_output("save_transcription", SaveInput({}), SaveOutput(OUTPUT_PATH), tmp_path)["valid"]
    assert not verify_task("transcribe-exams", TranscribeInput(), SaveOutput(OUTPUT_PATH), None, tmp_path)["valid"]
