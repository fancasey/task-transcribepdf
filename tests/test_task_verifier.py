"""Replay reference packets and challenge the public task verifier offline."""

import json
from pathlib import Path

import pytest
from slimconfig import build_output

from contract import SaveInput, TranscribeInput, TranscribeOutput
from plugin.transcribe import save_transcription
from verifier import transcribe, verify_task

DATA = Path(__file__).resolve().parents[1] / "src/plugin/data"
QUESTIONS = "transcriptions/alg2/questions.json"
RUBRIC = "transcriptions/alg2/rubric.json"
STUDENT = "transcriptions/alg2/students/1.json"


def save_packet(workspace, arguments):
    files = []
    for subject, students, source_folder in (
        ("ela", arguments.ela_students, "student_responses"),
        ("alg2", arguments.math_students, "students"),
    ):
        if not students:
            continue
        documents = [
            ("questions", None, DATA / subject / "reference/questions.json"),
            ("rubric", None, DATA / subject / "reference/rubric.json"),
            *(
                ("student_response", student, DATA / subject / source_folder / "reference" / f"{student}.json")
                for student in students
            ),
        ]
        for kind, student, reference in documents:
            value = json.loads(reference.read_text(encoding="utf-8"))
            saved = save_transcription(
                SaveInput(subject, kind, student, value["questions"], value["supplementary_info"]), workspace
            )
            filename = f"students/{student}.json" if student else f"{kind}.json"
            assert saved.path == f"transcriptions/{subject}/{filename}"
            files.append(saved.path)
    return TranscribeOutput("transcriptions", files)


def verify(workspace, arguments, output):
    return verify_task("transcribe-exams", arguments, output, None, workspace)


@pytest.fixture
def math_packet(tmp_path):
    arguments = TranscribeInput([], ["1"])
    return arguments, save_packet(tmp_path, arguments)


@pytest.mark.parametrize(
    ("ela", "math", "file_count"),
    [
        (["92"], [], 3),
        ([], ["6"], 3),
        (["99"], ["1"], 6),
        (["92", "93", "94", "95", "96", "97", "98", "99"], ["1", "2", "3", "4", "5", "6"], 18),
    ],
    ids=["ela-only", "math-only", "both", "full-roster"],
)
def test_reference_packets_pass_even_with_reordered_manifest(tmp_path, ela, math, file_count):
    arguments = TranscribeInput(ela, math)
    output = save_packet(tmp_path, arguments)
    assert len(output.files) == len(set(output.files)) == file_count
    output.files.reverse()
    verdict = verify(tmp_path, arguments, output)
    assert verdict["valid"] is True
    assert verdict["score"] == 1
    assert verdict["details"]["issues"] == []


@pytest.mark.parametrize(
    ("ela", "math", "message"),
    [
        ([], [], "Select at least one student"),
        (["91"], [], "distinct valid student IDs for ela"),
        (["100"], [], "distinct valid student IDs for ela"),
        ([], ["0"], "distinct valid student IDs for alg2"),
        ([], ["7"], "distinct valid student IDs for alg2"),
        (["92", "92"], ["1"], "distinct valid student IDs for ela"),
        ([], ["1", "1"], "distinct valid student IDs for alg2"),
        (["1"], ["92"], "distinct valid student IDs for ela"),
    ],
)
def test_invalid_student_selections(tmp_path, ela, math, message):
    verdict = verify(tmp_path, TranscribeInput(ela, math), TranscribeOutput("transcriptions", []))
    assert verdict["valid"] is False
    assert verdict["score"] == 0
    assert message in verdict["message"]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b'{"questions":', "Expecting value"),
        (b"[]", "must be an object"),
        (b"null", "must be an object"),
        (b"\xff", "utf-8"),
        (b'{"questions": {}, "questions": {}}', "Duplicate JSON key 'questions'"),
        (b'{"questions": {"25": {}, "25": {}}}', "Duplicate JSON key '25'"),
        (b'{"questions": {"25": {"source_pages": [NaN]}}}', "Invalid JSON constant NaN"),
        (b'{"questions": {"25": {"source_pages": [Infinity]}}}', "Invalid JSON constant Infinity"),
        (b'{"questions": {"25": {"source_pages": [-Infinity]}}}', "Invalid JSON constant -Infinity"),
    ],
)
def test_malformed_saved_file_gets_a_file_penalty(tmp_path, math_packet, payload, message):
    arguments, output = math_packet
    (tmp_path / QUESTIONS).write_bytes(payload)
    verdict = verify(tmp_path, arguments, output)
    assert verdict["valid"] is False
    assert verdict["score"] == pytest.approx(2 / 3)
    details = verdict["details"]
    assert details["organization_penalty"] == 100
    assert details["transcription_penalty"] == 0
    (issue,) = details["issues"]
    assert issue["path"] == QUESTIONS
    assert issue["penalty"] == 100
    assert message in issue["issue"]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"files": [QUESTIONS]},
        {"folder": "transcriptions", "files": QUESTIONS},
        {"folder": "transcriptions", "files": [None]},
        {"folder": "transcriptions", "files": [QUESTIONS], "score": 1},
    ],
    ids=["null", "missing-folder", "files-string", "null-path", "extra-field"],
)
def test_malformed_manifest_is_rejected_by_output_contract(payload):
    with pytest.raises(ValueError, match="TranscribeOutput"):
        build_output(payload, TranscribeOutput)


@pytest.mark.parametrize(
    ("folder", "files", "path", "message"),
    [
        ("wrong", [QUESTIONS, RUBRIC, STUDENT], "folder", "Wrong output folder"),
        ("transcriptions", [QUESTIONS, RUBRIC], STUDENT, "Saved file omitted from submission"),
        ("transcriptions", [QUESTIONS, RUBRIC, STUDENT, STUDENT], STUDENT, "duplicate submitted path"),
        (
            "transcriptions",
            [QUESTIONS, RUBRIC, STUDENT, "../outside.json"],
            "../outside.json",
            "Unexpected or duplicate submitted path",
        ),
    ],
    ids=["wrong-folder", "omitted-path", "duplicate-path", "traversal-path"],
)
def test_wrong_manifest_gets_an_organization_penalty(tmp_path, math_packet, folder, files, path, message):
    arguments, _ = math_packet
    output = build_output({"folder": folder, "files": files}, TranscribeOutput)
    verdict = verify(tmp_path, arguments, output)
    assert verdict["valid"] is False
    assert verdict["score"] == pytest.approx(290 / 300)
    (issue,) = verdict["details"]["issues"]
    assert issue["category"] == "organization"
    assert issue["penalty"] == 10
    assert issue["path"] == path
    assert message in issue["issue"]


@pytest.mark.parametrize("replacement", ["missing", "directory", "symlink"])
def test_unavailable_expected_file_is_rejected(tmp_path, math_packet, replacement):
    arguments, output = math_packet
    target = tmp_path / QUESTIONS
    original = target.read_bytes()
    target.unlink()
    if replacement == "directory":
        target.mkdir()
    elif replacement == "symlink":
        outside = tmp_path / "outside.json"
        outside.write_bytes(original)
        target.symlink_to(outside)
    verdict = verify(tmp_path, arguments, output)
    assert verdict["valid"] is False
    assert verdict["score"] == pytest.approx(2 / 3)
    assert verdict["details"]["issues"] == [
        {"category": "organization", "penalty": 100, "path": QUESTIONS, "issue": f"Missing or unsafe path {QUESTIONS}"}
    ]


@pytest.mark.parametrize(
    ("field", "replacement"),
    [("prompt", None), ("source_pages", [True]), ("source_pages", [1.0]), ("source_pages", [2])],
    ids=["null-prompt", "boolean-page", "float-page", "wrong-page"],
)
def test_wrong_nested_field_is_structural(tmp_path, math_packet, field, replacement):
    arguments, output = math_packet
    path = tmp_path / QUESTIONS
    document = json.loads(path.read_text(encoding="utf-8"))
    document["questions"]["25"][field] = replacement
    path.write_text(json.dumps(document), encoding="utf-8")
    verdict = verify(tmp_path, arguments, output)
    assert verdict["valid"] is False
    assert verdict["score"] == pytest.approx(290 / 300)
    (issue,) = verdict["details"]["issues"]
    assert issue["category"] == "organization"
    assert issue["penalty"] == 10
    assert issue["path"] == f"{QUESTIONS}.questions.25.{field}"


@pytest.mark.parametrize(("extra_words", "score"), [(1, 299.75 / 300), (1199, 0.25 / 300), (1200, 0), (1201, 0)])
def test_score_boundary_for_structurally_valid_wrong_text(tmp_path, math_packet, extra_words, score):
    arguments, output = math_packet
    path = tmp_path / QUESTIONS
    document = json.loads(path.read_text(encoding="utf-8"))
    document["questions"]["25"]["prompt"] += " fabricated" * extra_words
    path.write_text(json.dumps(document), encoding="utf-8")
    verdict = verify(tmp_path, arguments, output)
    assert verdict["valid"] is True
    assert verdict["score"] == pytest.approx(score)
    details = verdict["details"]
    assert details["organization_penalty"] == 0
    assert details["transcription_penalty"] == details["total_penalty"] == extra_words / 4
    assert details["issues"] == [
        {
            "category": "transcription",
            "penalty": extra_words / 4,
            "path": f"{QUESTIONS}.questions.25.prompt",
            "issue": "Text differs",
        }
    ]


@pytest.mark.parametrize(
    ("question", "expected_penalty", "has_advisory_penalty"),
    [("25", 0.25, False), ("26", 0, True)],
    ids=["manual-reference", "ocr-reference"],
)
def test_reference_controls_which_student_text_is_scored(
    tmp_path, math_packet, monkeypatch, question, expected_penalty, has_advisory_penalty
):
    arguments, output = math_packet
    if has_advisory_penalty:
        references = dict(transcribe.packet_documents(arguments))
        student_path = Path(STUDENT)
        reference = json.loads(references[student_path].read_text(encoding="utf-8"))
        reference["questions"][question]["response_segments"][0]["transcription_method"] = "ocr"
        fixture = tmp_path / "ocr-reference.json"
        fixture.write_text(json.dumps(reference), encoding="utf-8")
        references[student_path] = fixture
        monkeypatch.setattr(transcribe, "packet_documents", lambda _: references.items())

    path = tmp_path / STUDENT
    document = json.loads(path.read_text(encoding="utf-8"))
    segment = document["questions"][question]["response_segments"][0]
    segment["text"] += " fabricated"
    segment["transcription_method"] = "manual" if has_advisory_penalty else "ocr"
    path.write_text(json.dumps(document), encoding="utf-8")

    verdict = verify(tmp_path, arguments, output)
    assert verdict["valid"] is True
    assert verdict["score"] == pytest.approx(1 - expected_penalty / 300)
    details = verdict["details"]
    assert details["organization_penalty"] == 0
    assert details["transcription_penalty"] == expected_penalty
    assert (details["ocr_advisory_penalty"] > 0) is has_advisory_penalty
    assert [issue["path"] for issue in details["issues"]] == (
        [] if has_advisory_penalty else [f"{STUDENT}.questions.{question}.response_segments[1].text"]
    )
