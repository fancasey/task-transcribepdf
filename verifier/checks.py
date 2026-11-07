"""Read and validate saved JSON."""

import json
from pathlib import Path


def result(valid, message, *, score=None, **details):
    return {"valid": valid, "score": float(valid) if score is None else score, "message": message, "details": details}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key {key!r}")
        value[key] = item
    return value


def load_saved(workspace, relative):
    path = Path(workspace).resolve() / relative
    if path.resolve() != path:
        raise ValueError(f"Unsafe path {relative}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
