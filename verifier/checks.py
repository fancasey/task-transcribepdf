"""Shared deterministic checks for tool inputs and saved files."""

import json
from pathlib import Path

from contract import DOCUMENT_TYPES, OUTPUT_FOLDER, STUDENT_IDS


def result(valid, message, *, score=None, **details):
    return {"valid": valid, "score": float(valid) if score is None else score, "message": message, "details": details}


def document_problem(value):
    if value.subject not in STUDENT_IDS or value.document_type not in DOCUMENT_TYPES:
        return "Choose ela or alg2 and a supported document type"
    if value.document_type == "student_response":
        if value.student_id not in STUDENT_IDS[value.subject]:
            return f"Unknown student ID for {value.subject}"
    elif value.student_id is not None:
        return "Only student responses take a student ID"
    return None


def output_path(subject, document_type, student_id=None):
    folder = Path(OUTPUT_FOLDER) / subject
    if document_type == "student_response":
        return folder / "students" / f"{student_id}.json"
    return folder / f"{document_type}.json"


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key {key!r}")
        value[key] = item
    return value


def reject_json_constant(value):
    raise ValueError(f"Invalid JSON constant {value}")


def load_saved(workspace, relative):
    workspace = Path(workspace).resolve()
    path = workspace / relative
    if path.resolve() != path or not path.is_file():
        raise ValueError(f"Missing or unsafe path {relative}")
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=reject_json_constant
    )
    if not isinstance(value, dict):
        raise TypeError("Saved transcription must be an object")
    return value
