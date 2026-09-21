# agent/tool_executor.py

from langchain_core.messages import ToolMessage

from tools import INVESTIGATION_TOOLS

try:
    from agent.evidence_builder import (
        tool_result_to_evidence,
    )
except ImportError:
    from evidence_builder import (
        tool_result_to_evidence,
    )


TOOL_MAP = {
    tool.name: tool
    for tool in INVESTIGATION_TOOLS
}


class ToolExecutor:

    def execute(self, tool_call):

        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id", "")

        # -----------------------------------------
        # Validate tool
        # -----------------------------------------

        if tool_name not in TOOL_MAP:
            raise ValueError(
                f"Unknown investigation tool: {tool_name}"
            )

        tool = TOOL_MAP[tool_name]

        # -----------------------------------------
        # Execute tool
        # -----------------------------------------

        result = tool.invoke(tool_args)

        # -----------------------------------------
        # Convert result into persistent evidence
        # -----------------------------------------

        evidence = tool_result_to_evidence(
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
        )

        # -----------------------------------------
        # Message returned to LLM
        # -----------------------------------------

        tool_message = ToolMessage(
            content=str(result),
            tool_call_id=tool_call_id,
        )

        return {
            "tool": tool_name,
            "args": tool_args,
            "result": result,
            "tool_call_id": tool_call_id,
            "message": tool_message,
            "evidence": evidence,
        }

    def execute_all(self, tool_calls):

        results = []

        for tool_call in tool_calls:

            result = self.execute(
                tool_call
            )

            results.append(result)

        return results

    def node(self, state):

        messages = list(state.get("messages", []))

        if not messages:
            return {}

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", None) or []

        if not tool_calls:
            return {}

        new_messages = []
        new_evidence = []
        new_tools_used = []
        new_evidence_requests = []

        for tool_call in tool_calls:
            execution = self.execute(tool_call)
            new_messages.append(execution["message"])
            new_evidence.append(execution["evidence"])
            new_tools_used.append(execution["tool"])
            result_dict = execution.get("result")
            if isinstance(result_dict, dict) and "request_type" in result_dict:
                new_evidence_requests.append(result_dict)

        updates = {
            "messages": messages + new_messages,
            "evidence": list(state.get("evidence", [])) + new_evidence,
            "tools_used": list(state.get("tools_used", [])) + new_tools_used,
        }
        if new_evidence_requests:
            updates["evidence_requests"] = list(state.get("evidence_requests", [])) + new_evidence_requests

        return updates