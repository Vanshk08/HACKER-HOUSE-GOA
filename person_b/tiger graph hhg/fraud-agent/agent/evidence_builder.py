# agent/evidence_builder.py

try:
    from investigation.evidence import Evidence
except ImportError:
    from agent.state import Evidence


def tool_result_to_evidence(
    tool_name,
    tool_args,
    result,
) -> Evidence:

    return {
        "id": f"tool:{tool_name}",
        "source": tool_name,
        "type": "tool_result",
        "description": f"Evidence returned by {tool_name}",
        "data": {
            "arguments": tool_args,
            "result": result,
        },
        "confidence": 1.0,
    }