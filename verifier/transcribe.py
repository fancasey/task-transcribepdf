"""Compare saved transcriptions with the supplied reference packet."""

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from unicodedata import normalize

from contract import OUTPUT_FOLDER, STUDENT_IDS, SUBJECTS

from .checks import load_saved, output_path, result

DATA = Path("src/plugin/data")
ORGANIZATION_WEIGHT = 10
FILE_WEIGHT = 100
TOKEN_WEIGHT = 0.25
CRITICAL_WEIGHT = 0.75
IGNORED = {"transcription_method", "transcription_notes", "review_note", "visual_note"}
CRITICAL = re.compile(r"\d|^[+\-*/=^<>≤≥±√×÷−°%()\[\]]$")
TOKEN = re.compile(r"\d+(?:\.\d+)?|[^\W\d_]+(?:'[^\W\d_]+)?|[^\s]", re.UNICODE)
SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
GLYPHS = str.maketrans({"−": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "×": "*", "·": "*", "÷": "/"})
SIMPLE_POWER = re.compile(r"\^\s*(?:\(\s*([+-]?\s*\d+)\s*\)|\{\s*([+-]?\s*\d+)\s*\})")


def tokens(value):
    value = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+", lambda m: "^" + m.group().translate(SUPER), value)
    value = normalize("NFC", value).translate(GLYPHS).replace("\u00ad", "")
    value = SIMPLE_POWER.sub(lambda match: "^" + (match[1] or match[2]), value)
    return TOKEN.findall(value)


def edit_penalty(expected, actual):
    """Weighted edit distance with a higher cost for math and numeric edits."""
    prefix = 0
    for left, right in zip(expected, actual):
        if left != right:
            break
        prefix += 1
    expected, actual = expected[prefix:], actual[prefix:]
    while expected and actual and expected[-1] == actual[-1]:
        expected.pop()
        actual.pop()
    weights = [CRITICAL_WEIGHT if CRITICAL.search(token) else TOKEN_WEIGHT for token in actual]
    row = [0]
    for weight in weights:
        row.append(row[-1] + weight)
    for left in expected:
        left_weight = CRITICAL_WEIGHT if CRITICAL.search(left) else TOKEN_WEIGHT
        next_row = [row[0] + left_weight]
        for index, (right, right_weight) in enumerate(zip(actual, weights), start=1):
            next_row.append(
                min(
                    row[index] + left_weight,
                    next_row[-1] + right_weight,
                    row[index - 1] + (0 if left == right else max(left_weight, right_weight)),
                )
            )
        row = next_row
    return row[-1]


def fingerprint(value):
    if isinstance(value, dict):
        return tuple((key, fingerprint(item)) for key, item in sorted(value.items()) if key not in IGNORED)
    if isinstance(value, list):
        return tuple(map(fingerprint, value))
    if isinstance(value, str):
        return tuple(tokens(value))
    return value


def compare_sequence(expected, actual, path, findings):
    left = list(map(fingerprint, expected))
    right = list(map(fingerprint, actual))
    if left != right and Counter(left) == Counter(right):
        findings.append(("organization", ORGANIZATION_WEIGHT, path, "Items are out of order"))
        return
    if len(left) == len(right):
        for index, (wanted, found) in enumerate(zip(expected, actual)):
            compare(wanted, found, f"{path}[{index + 1}]", findings)
        return
    # Anchor exact items so a missing entry does not shift every later comparison.
    for _, i, j, k, end in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        for offset, (wanted, found) in enumerate(zip(expected[i:j], actual[k:end])):
            compare(wanted, found, f"{path}[{i + offset + 1}]", findings)
        for _ in range(abs((j - i) - (end - k))):
            findings.append(("organization", ORGANIZATION_WEIGHT, path, "Missing or extra list item"))


def compare(expected, actual, path, findings, field=""):
    if type(expected) is not type(actual):
        findings.append(("organization", ORGANIZATION_WEIGHT, path, "Wrong value type"))
    elif isinstance(expected, dict):
        labels = {}
        if field in {"questions", "subitems", "criteria_by_score", "score_descriptors"}:
            for key, value in expected.items():
                labels.setdefault(fingerprint(value), []).append(key)
        weak_text = expected.get("transcription_method") in {"ocr", "no_text_recognized"}
        for key in sorted((expected.keys() | actual.keys()) - IGNORED):
            child = f"{path}.{key}"
            if key == "text" and weak_text and isinstance(actual.get(key), str):
                points = edit_penalty(tokens(expected[key]), tokens(actual[key]))
                findings.append(("ocr_advisory", points, child, "Reference text is unverified OCR"))
            elif key not in expected or key not in actual:
                findings.append(("organization", ORGANIZATION_WEIGHT, child, "Missing or extra field"))
            elif labels and key not in labels.get(fingerprint(actual[key]), [key]):
                findings.append(("organization", ORGANIZATION_WEIGHT, child, "Content belongs under another label"))
            else:
                compare(expected[key], actual[key], child, findings, key)
    elif field in {
        "part",
        "kind",
        "source_page",
        "source_pages",
        "page_count",
        "source",
        "student_id",
        "document_type",
    }:
        if expected != actual or (field == "source_pages" and any(type(page) is not int for page in actual)):
            findings.append(("organization", ORGANIZATION_WEIGHT, path, "Wrong label or source location"))
    elif isinstance(expected, list):
        compare_sequence(expected, actual, path, findings)
    elif isinstance(expected, str):
        points = edit_penalty(tokens(expected), tokens(actual))
        if points:
            findings.append(("transcription", points, path, "Text differs"))
    elif expected != actual:
        findings.append(("transcription", CRITICAL_WEIGHT, path, "Value differs"))


def packet_documents(arguments):
    for subject, students in (("ela", arguments.ela_students), ("alg2", arguments.math_students)):
        if not students:
            continue
        for kind in ("questions", "rubric"):
            yield output_path(subject, kind), DATA / subject / "reference" / f"{kind}.json"
        for student in students:
            relative = output_path(subject, "student_response", student)
            yield relative, DATA / subject / SUBJECTS[subject] / "reference" / relative.name


def verify_task(arguments, output, reference, workspace):
    selections = {"ela": arguments.ela_students, "alg2": arguments.math_students}
    if not any(selections.values()):
        return result(False, "Select at least one student")
    for subject, students in selections.items():
        if len(students) != len(set(students)) or any(student not in STUDENT_IDS[subject] for student in students):
            return result(False, f"Select distinct valid student IDs for {subject}")

    documents = dict(packet_documents(arguments))
    expected_paths = {path.as_posix() for path in documents}
    submitted = Counter(output.files)
    findings = []
    if output.folder != OUTPUT_FOLDER:
        findings.append(("organization", ORGANIZATION_WEIGHT, "folder", "Wrong output folder"))
    for path, count in sorted(submitted.items()):
        if path not in expected_paths or count != 1:
            findings.append(("organization", ORGANIZATION_WEIGHT, path, "Unexpected or duplicate submitted path"))
    folder = Path(workspace).resolve() / OUTPUT_FOLDER
    if folder.resolve() == folder:
        for path in sorted(folder.rglob("*.json")):
            relative = path.relative_to(folder.parent).as_posix()
            if relative not in expected_paths and relative not in submitted:
                findings.append(("organization", ORGANIZATION_WEIGHT, relative, "Unexpected saved file"))
    for relative, reference_path in documents.items():
        path = relative.as_posix()
        try:
            actual = load_saved(workspace, relative)
        except (OSError, TypeError, ValueError) as error:
            findings.append(("organization", FILE_WEIGHT, path, str(error)))
            continue
        if path not in submitted:
            findings.append(("organization", ORGANIZATION_WEIGHT, path, "Saved file omitted from submission"))
        expected = json.loads(reference_path.read_text(encoding="utf-8"))
        compare(expected, actual, path, findings)

    totals = Counter()
    for category, points, _, _ in findings:
        totals[category] += points
    organization = totals["organization"]
    transcription = totals["transcription"]
    total = organization + transcription
    issues = [
        {"category": category, "penalty": points, "path": path, "issue": message}
        for category, points, path, message in findings
        if category != "ocr_advisory"
    ]
    return result(
        organization == 0,
        f"{organization} organization penalty points and {transcription} transcription penalty points",
        score=max(0, 1 - total / (FILE_WEIGHT * len(documents))),
        organization_penalty=organization,
        transcription_penalty=transcription,
        total_penalty=total,
        ocr_advisory_penalty=totals["ocr_advisory"],
        ocr_advisory_segments=sum(category == "ocr_advisory" for category, _, _, _ in findings),
        issues=issues,
    )
