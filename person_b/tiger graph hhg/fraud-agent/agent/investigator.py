# agent/investigator.py

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
)

from tools import INVESTIGATION_TOOLS


INVESTIGATOR_SYSTEM_PROMPT = """
You are the Investigation Agent in a financial fraud investigation system.

Your job is to investigate the assigned case by gathering and interpreting
evidence.

You are an INVESTIGATOR, not the final policy decision maker.

You should:

1. Understand the case.
2. Examine available evidence.
3. Generate competing hypotheses.
4. Consider both fraudulent and legitimate explanations.
5. Select investigation tools when additional evidence is needed.
6. Interpret returned evidence.
7. Identify supporting and contradicting evidence.
8. Continue while decision-relevant uncertainty remains.
9. Stop when enough evidence has been gathered.

Important rules:

- Risk score is a reason to investigate, NOT a fraud verdict.
- Previous fraud is not proof that the current transaction is fraud.
- Closed cases provide context, not automatic labels.
- Graph connections are not automatically evidence of fraud.
- Never invent IDs or evidence.
- Always consider legitimate explanations.
- Use tools selectively.
- Do not make final policy decisions.
- If important external evidence is missing, identify it explicitly.

If you are finished investigating, return a final response WITHOUT
requesting any tools.

If you still need evidence, use the appropriate tools.
"""


class InvestigationAgent:

    def __init__(self, llm):

        self.llm = llm.bind_tools(
            INVESTIGATION_TOOLS
        )

    def node(self, state):

        messages = state.get("messages", [])

        # First invocation
        if not messages:

            messages = [
                SystemMessage(
                    content=INVESTIGATOR_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=self._build_case_context(state)
                ),
            ]

        response = self.llm.invoke(messages)

        updates = {
            "messages": messages + [response],
            "iteration_count": (
                state.get("iteration_count", 0) + 1
            ),
        }

        if hasattr(response, "hypotheses") and response.hypotheses:
            updates["hypotheses"] = response.hypotheses
        elif "hypotheses" in getattr(response, "additional_kwargs", {}):
            updates["hypotheses"] = response.additional_kwargs["hypotheses"]

        if hasattr(response, "evidence_requests") and response.evidence_requests:
            updates["evidence_requests"] = response.evidence_requests
        elif "evidence_requests" in getattr(response, "additional_kwargs", {}):
            updates["evidence_requests"] = response.additional_kwargs["evidence_requests"]

        return updates

    def _build_case_context(self, state):
        trigger_type = state.get("trigger_type")
        trigger_text = state.get("trigger_text")
        risk_score = state.get("risk_score")
        extra = ""
        if trigger_type:
            extra += f"trigger_type: {trigger_type}\n"
        if trigger_text:
            extra += f"trigger_text: {trigger_text}\n"
        if risk_score is not None:
            extra += f"risk_score: {risk_score}\n"

        return f"""
CASE

case_id: {state.get("case_id")}
customer_id: {state.get("customer_id")}
card_id: {state.get("card_id")}
flagged_txn_id: {state.get("flagged_txn_id")}
{extra}
CURRENT EVIDENCE:
{state.get("evidence", [])}

CURRENT HYPOTHESES:
{state.get("hypotheses", [])}

CURRENT ASSESSMENT:
{state.get("assessment", {})}

EVIDENCE REQUESTS:
{state.get("evidence_requests", [])}

TOOLS USED:
{state.get("tools_used", [])}
"""