"""Check exam question structure and spot-check the extracted prose."""

import re

from contract import OUTPUT_PATH, QUESTION_PAGES
from plugin.validation import validate_interval

from .checks import load_saved, result

# Only these questions have distinct response prompts in the printed exam.
SUBQUESTION_ANCHORS = {
    "34": ("State the period", "State the amplitude", "represent the sinusoidal function"),
    "35": ("middle 95% of simulated proportions", "support the superintendent's concern"),
    "36": (
        "when Lubin poured it into the cup",
        "average rate of change in degrees per minute",
        "Interpret the value of the average rate of change",
        "reaches 120",
    ),
}
TEXT_WEIGHT = 0.20

# Use prose fragments so symbol extraction, spacing, and chart layout do not affect the check.
PROMPT_ANCHORS = (
    "The expression",
    "Which statement is true about the graph",
    "An exponential function that contains the points",
    "A and B are two events",
    "is in the solution set",
    "Consider the recursive formula",
    "Antonella is solving a system",
    "is equivalent to",
    "Which statement is true for the graph",
    "The solution set to the equation",
    "The value of",
    "Mark purchased a new car",
    "their favorite subject",
    "For the polynomial",
    "in standard position",
    "The solution set to the equation",
    "ketchup packets",
    "A school counselor wants to estimate",
    "The sport of pickleball",
    "The solutions to",
    "The completely factored form",
    "Which function is odd",
    "What is the inverse",
    "has a period of",
    "a grocery store manager",
    "express the result in standard form",
    "Determine algebraically the zeros",
    "On the same set of axes",
    "in simplest",
    "The half-life of cesium",
    "Solve algebraically",
    "rounding values to the nearest thousandth",
    "Determine the quotient and remainder",
    "The sinusoidal function",
    "A principal wonders",
    "Lubin pours green tea",
)


def words(value):
    return " " + " ".join(re.findall(r"\w+", value.casefold())) + " "




def verify_task(output, workspace, arguments):
    try:
        validate_interval(arguments.start_page, arguments.end_page)
    except ValueError as error:
        return result(False, str(error))
    if output.path != OUTPUT_PATH:
        return result(False, f"Return the saved path {OUTPUT_PATH}")
    try:
        saved = load_saved(workspace, OUTPUT_PATH)
    except (OSError, ValueError) as error:
        return result(False, f"Could not read organized questions: {error}")
    if not isinstance(saved, dict) or not isinstance(saved.get("questions"), dict):
        return result(False, "Saved JSON must contain a questions object")

    if (saved.get("start_page"), saved.get("end_page")) != (arguments.start_page, arguments.end_page):
        return result(False, "Saved page interval differs from the requested interval")
    actual = saved["questions"]
    expected = {str(number): anchor for number, anchor in enumerate(PROMPT_ANCHORS, 1)
                if all(arguments.start_page <= page <= arguments.end_page for page in QUESTION_PAGES[str(number)])}
    missing = [key for key in expected if key not in actual]
    unexpected = sorted(actual.keys() - expected.keys())
    invalid = []
    subquestion_counts = {}
    text_warnings = []
    for key, anchor in expected.items():
        if key not in actual:
            continue
        question = actual[key]
        if (
            not isinstance(question, dict)
            or question.get("pages") != QUESTION_PAGES[key]
            or not isinstance(question.get("prompt"), str)
            or not question["prompt"].strip()
            or not isinstance(question.get("subquestions"), list)
            or any(not isinstance(part, str) or not part.strip() for part in question["subquestions"])
        ):
            invalid.append(key)
            continue
        parts = question["subquestions"]
        anchors = SUBQUESTION_ANCHORS.get(key, ())
        if len(parts) != len(anchors):
            subquestion_counts[key] = {"expected": len(anchors), "actual": len(parts)}
        if words(anchor) not in words(question["prompt"]):
            text_warnings.append(key)
        for index, (part, fragment) in enumerate(zip(parts, anchors), 1):
            if words(fragment) not in words(part):
                text_warnings.append(f"{key}.{index}")

    valid = not (missing or unexpected or invalid or subquestion_counts)
    phrase_count = len(expected) + sum(len(SUBQUESTION_ANCHORS.get(key, ())) for key in expected)
    score = 1 - TEXT_WEIGHT * len(text_warnings) / max(1, phrase_count) if valid else 0
    return result(
        valid,
        "Question and subquestion counts match" if valid else "Exam question structure differs from the reference",
        score=score,
        missing=missing,
        unexpected=unexpected,
        invalid=invalid,
        subquestion_counts=subquestion_counts,
        text_warnings=text_warnings,
    )
