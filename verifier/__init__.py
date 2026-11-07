"""NanoAgent's deterministic verification entry points."""

from dataclasses import asdict

from contract import MAX_PAGES_PER_READ, OUTPUT_PATH, Task, Tool
from plugin.validation import validate_save

from . import transcribe
from .checks import load_saved, result


def verify_input(tool, value):
    if Tool(tool) is Tool.READ_PDF:
        pages = value.pages
        if not 1 <= len(pages) <= MAX_PAGES_PER_READ or pages != sorted(set(pages)) or pages[0] < 1:
            return result(False, "Request one to five distinct positive pages in increasing order")
    else:
        try:
            validate_save(value)
        except ValueError as error:
            return result(False, str(error))
    return result(True, "Valid request")


def verify_output(tool, input_value, output_value, workspace):
    if Tool(tool) is Tool.READ_PDF:
        valid = (
            [page.page for page in output_value.pages] == input_value.pages
            and all(1 <= page.page <= output_value.page_count for page in output_value.pages)
        )
        return result(valid, "PDF pages returned in requested order" if valid else "PDF page output differs from request")
    if output_value.path != OUTPUT_PATH:
        return result(False, "Unexpected output path")
    try:
        saved = load_saved(workspace, OUTPUT_PATH)
    except (OSError, ValueError) as error:
        return result(False, str(error))
    valid = saved == asdict(input_value)
    return result(valid, "Questions saved" if valid else "Saved questions differ from tool input")


def verify_task(task, arguments, output, reference, workspace):
    Task(task)
    return transcribe.verify_task(output, workspace, arguments)
