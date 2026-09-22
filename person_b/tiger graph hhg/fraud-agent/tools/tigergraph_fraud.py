"""Person B tool for graph evidence provided by Person A over MCP."""

import asyncio
import json
import os
import sys
from typing import Any

from langchain_core.tools import tool


def _decode_mcp_result(result: Any) -> dict[str, Any]:
    """Convert MCP content blocks into the normal tool result dictionary."""
    if isinstance(result, dict):
        return result

    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded

    raise RuntimeError("Person A MCP returned no JSON graph investigation result")


async def _call_person_a_mcp_async(transaction_id: str) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "person_a.mcp.server"],
        env={**os.environ, "PYTHONPATH": project_root},
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "analyze_transaction",
                {"transaction_id": str(transaction_id).strip()},
            )
            return _decode_mcp_result(result)


def _call_person_a_mcp(transaction_id: str) -> dict[str, Any]:
    """Synchronously bridge the LangChain tool call to Person A's MCP server."""
    return asyncio.run(_call_person_a_mcp_async(transaction_id))


@tool
def investigate_transaction_graph(transaction_id: str) -> dict[str, Any]:
    """Retrieve graph-based evidence from Person A through MCP.

    Returns transaction information, graph features, linked cards, related
    transactions, network signals, and fraud signals. This tool returns
    evidence only and does not make the final fraud or policy decision.
    """
    return _call_person_a_mcp(transaction_id)