"""NanoAgent's deterministic verification entry points."""

from contract import MAX_PAGES_PER_READ, Task, Tool

from . import transcribe
from .checks import document_problem, load_saved, output_path, result


def verify_input(tool, value):
    problem = document_problem(value)
    if problem:
        return result(False, problem)
    if Tool(tool) is Tool.READ_PDF:
        pages = value.pages
        if not 1 <= len(pages) <= MAX_PAGES_PER_READ or pages != sorted(set(pages)) or pages[0] < 1:
            return result(False, "Request one to three distinct positive pages in increasing order")
    elif any(not key.isdecimal() or not isinstance(record, dict) for key, record in value.questions.items()):
        return result(False, "questions must map numeric question IDs to objects")
    return result(True, "Valid document request")


def verify_output(tool, input_value, output_value, workspace):
    if Tool(tool) is Tool.READ_PDF:
        valid = (
            [page.page for page in output_value.pages] == input_value.pages
            and len(output_value.images) == len(input_value.pages)
            and all(1 <= page.page <= output_value.page_count for page in output_value.pages)
            and all(
                image.media_type == "image/png" and image.data.startswith("iVBORw0KGgo")
                for image in output_value.images
            )
        )
        return result(
            valid, "PDF pages returned in requested order" if valid else "PDF page output differs from request"
        )
    relative = output_path(input_value.subject, input_value.document_type, input_value.student_id)
    if output_value.path != relative.as_posix():
        return result(False, "Transcription path differs from requested document")
    try:
        saved = load_saved(workspace, relative)
    except (OSError, TypeError, ValueError) as error:
        return result(False, str(error))
    valid = (
        saved.get("document_type") == input_value.document_type
        and saved.get("student_id") == input_value.student_id
        and saved.get("questions") == input_value.questions
        and saved.get("supplementary_info") == input_value.supplementary_info
    )
    return result(valid, "Transcription saved" if valid else "Saved transcription differs from tool input")


def verify_task(task, arguments, output, reference, workspace):
    Task(task)
    return transcribe.verify_task(arguments, output, reference, workspace)
