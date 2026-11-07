import asyncio
import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from contract import OUTPUT_PATH, ReadInput, TranscribeInput
from plugin.transcribe import read_pdf


def test_mcp_reads_exam_and_saves_organized_questions(tmp_path):
    expected = {"start_page": 1, "end_page": 5, "questions": {"1": {"prompt": "The expression", "subquestions": [], "pages": [2]}}}

    async def call():
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "plugin"], env={"NANOAGENT_WORKSPACE": str(tmp_path)}
        )
        async with stdio_client(parameters) as (reader, writer), ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool("read_pdf", {"pages": [2, 22, 23]})
            assert not result.isError
            data = result.structuredContent
            assert data["page_count"] == 28
            assert [page["page"] for page in data["pages"]] == [2, 22, 23]
            assert "An exponential function" in data["pages"][0]["text"]
            assert "Question 36 continued" in data["pages"][2]["text"]
            assert "images" not in data

            result = await session.call_tool("save_transcription", expected)
            assert not result.isError
            assert result.structuredContent == {"path": OUTPUT_PATH, "transcription": expected}

    asyncio.run(call())
    assert json.loads((tmp_path / OUTPUT_PATH).read_text(encoding="utf-8")) == expected
    assert vars(TranscribeInput(1, 5)) == {"start_page": 1, "end_page": 5}


@pytest.mark.parametrize("pages", [[], [0], [1, 1], [2, 1], [1, 2, 3, 4, 5, 6], [29]])
def test_reader_rejects_invalid_batches(tmp_path, pages):
    with pytest.raises(ValueError):
        read_pdf(ReadInput(pages), tmp_path)


def test_mcp_advertises_contracts_and_recovers_after_invalid_calls(tmp_path):
    async def call():
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "plugin"], env={"NANOAGENT_WORKSPACE": str(tmp_path)}
        )
        async with stdio_client(parameters) as (reader, writer), ClientSession(reader, writer) as session:
            await session.initialize()
            advertised = (await session.list_tools()).tools
            assert {tool.name for tool in advertised} == {"read_pdf", "save_transcription"}
            for tool in advertised:
                assert tool.inputSchema["type"] == "object"
                assert tool.outputSchema["type"] == "object"
            bad_calls = [
                ("unknown", {}),
                ("read_pdf", {}),
                ("read_pdf", {"pages": "1"}),
                ("read_pdf", {"pages": [0]}),
                ("read_pdf", {"pages": [29]}),
                ("read_pdf", {"pages": [2, 1]}),
                ("read_pdf", {"pages": [1, 1]}),
                ("read_pdf", {"pages": [1, 2, 3, 4, 5, 6]}),
                ("save_transcription", {"questions": {}}),
                ("save_transcription", {"questions": {"../1": {"prompt": "x", "subquestions": []}}}),
                ("save_transcription", {"questions": {"1": {"prompt": "x"}}}),
            ]
            for name, arguments in bad_calls:
                result = await session.call_tool(name, arguments)
                assert result.isError, (name, arguments, result)
            assert not (tmp_path / OUTPUT_PATH).exists()
            result = await session.call_tool("read_pdf", {"pages": [28]})
            assert not result.isError
            assert result.structuredContent["pages"][0]["page"] == 28

    asyncio.run(call())
