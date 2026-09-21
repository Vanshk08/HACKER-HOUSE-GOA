# agent/investigator.py

import json
import re
from typing import Any
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

from tools import INVESTIGATION_TOOLS
from investigation.hypotheses import Hypothesis


INVESTIGATOR_SYSTEM_PROMPT = """You are the Investigation Agent in a financial fraud investigation system.

Your job is to investigate the assigned case by actively deciding which investigation tools to call, gathering concrete evidence, and interpreting findings.

You are an INVESTIGATOR, not the final policy decision maker.

CRITICAL RESPONSIBILITIES:
1. TOOL SELECTION & EVIDENCE GATHERING:
   - Decide dynamically which investigation tools to call based on case context and returned evidence.
   - Call tools over multiple cycles as needed to test emerging leads.
   - Do NOT attempt to analyze the entire transaction database. Query specific tools for relevant cards, customers, devices, regions, or sequences.

2. COMPETING HYPOTHESES:
   - Actively generate, evaluate, and update COMPETING HYPOTHESES across multiple cycles:
     * Fraudulent explanation (e.g., unauthorized online access, counterfeit cloning, credential compromise).
     * Legitimate explanation (e.g., routine repeat behavior, known customer region, family member spend).
     * Undocumented or coordinated pattern when supported by evidence (e.g., syndicate ring, velocity bursts, shared origins).
   - Do NOT force the five known fraud patterns if the evidence points to a novel or different pattern.
   - Track both SUPPORTING and CONTRADICTING evidence for each hypothesis.

3. UNCERTAINTY & GROUNDING:
   - Ground all observations strictly in tool results. Never invent transaction IDs, amounts, or entities.
   - Risk score is a reason to investigate, NOT proof of fraud.
   - Closed cases provide historical precedent, NOT proof of current fraud.
   - If critical evidence is missing (such as cardholder authorization), explicitly register an evidence request.

4. SAFE STOPPING:
   - Stop when sufficient evidence has been gathered to evaluate the competing hypotheses, or when remaining uncertainty cannot be resolved by available tools.
   - When finished, return your final synthesis WITHOUT requesting any further tools.
   - Include your structured competing hypotheses in your concluding response in a JSON block:
```json
[
  {
    "id": "hyp_1_legitimate",
    "title": "Legitimate Customer Activity",
    "description": "...",
    "confidence": 0.6,
    "supporting_evidence": ["..."],
    "contradicting_evidence": ["..."]
  },
  {
    "id": "hyp_2_fraud",
    "title": "Unauthorized Fraud",
    "description": "...",
    "confidence": 0.4,
    "supporting_evidence": ["..."],
    "contradicting_evidence": ["..."]
  }
]
```
"""


class InvestigationAgent:

    def __init__(self, llm):
        if hasattr(llm, "bind_tools") and not getattr(llm, "_tools_bound", False):
            try:
                self.llm = llm.bind_tools(INVESTIGATION_TOOLS)
                setattr(self.llm, "_tools_bound", True)
            except Exception:
                self.llm = llm
        else:
            self.llm = llm

    def node(self, state: dict[str, Any]) -> dict[str, Any]:
        max_iterations = state.get("max_iterations", 10)
        iteration_count = state.get("iteration_count", 0)

        # Safe stop at max iterations
        if iteration_count >= max_iterations:
            return {
                "stop": True,
                "stop_reason": f"Maximum allowed investigation iterations ({max_iterations}) reached.",
            }

        messages = list(state.get("messages", []))

        # First invocation
        if not messages:
            messages = [
                SystemMessage(content=INVESTIGATOR_SYSTEM_PROMPT),
                HumanMessage(content=self._build_case_context(state)),
            ]
        elif iteration_count == max_iterations - 1:
            # Reaching max iterations: prompt the model to conclude without tools
            messages.append(
                HumanMessage(
                    content="You have reached the final investigation iteration. Synthesize all gathered evidence and evaluate your competing hypotheses. Do NOT request any additional tools."
                )
            )

        response = self.llm.invoke(messages)

        updates = {
            "messages": messages + [response],
            "iteration_count": iteration_count + 1,
        }

        # Extract hypotheses
        hypotheses = self._extract_hypotheses(response, state)
        if hypotheses:
            updates["hypotheses"] = hypotheses

        # Extract evidence requests
        if hasattr(response, "evidence_requests") and response.evidence_requests:
            updates["evidence_requests"] = response.evidence_requests
        elif "evidence_requests" in getattr(response, "additional_kwargs", {}):
            updates["evidence_requests"] = response.additional_kwargs["evidence_requests"]

        return updates

    def _extract_hypotheses(self, response: Any, state: dict[str, Any]) -> list[dict[str, Any]]:
        # 1. Direct attribute or additional_kwargs
        if hasattr(response, "hypotheses") and response.hypotheses:
            return response.hypotheses
        if "hypotheses" in getattr(response, "additional_kwargs", {}):
            return response.additional_kwargs["hypotheses"]

        # 2. Parse from response content if present
        content = getattr(response, "content", "")
        if isinstance(content, str) and content:
            # Check for ```json [...] ``` block
            match = re.search(r"```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```", content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed
                except Exception:
                    pass

            # Check for raw JSON array containing "title"
            match_raw = re.search(r"(\[\s*\{[\s\S]*?\"title\"[\s\S]*?\}\s*\])", content)
            if match_raw:
                try:
                    parsed = json.loads(match_raw.group(1))
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed
                except Exception:
                    pass

        # 3. If hypotheses already exist in state, preserve them
        existing = state.get("hypotheses", [])
        if existing:
            return existing

        # 4. If no tool calls in response (concluding turn), generate balanced competing hypotheses
        has_tool_calls = bool(getattr(response, "tool_calls", None))
        if not has_tool_calls:
            return self._generate_default_competing_hypotheses(state)

        return []

    def _generate_default_competing_hypotheses(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        trigger_type = state.get("trigger_type", "unknown")
        flagged_txn_id = state.get("flagged_txn_id", "unknown")
        is_customer_reported = (trigger_type == "customer_report") or ("never made this" in str(state.get("trigger_text", "")).lower())

        return [
            {
                "id": "hyp_1_legitimate_behavior",
                "title": "Legitimate Customer Activity",
                "description": "Transaction represents authorized customer spending consistent with established account behavior.",
                "confidence": 0.20 if is_customer_reported else 0.55,
                "supporting_evidence": ["Customer account has prior active legitimate history."],
                "contradicting_evidence": ["Customer reported unrecognized activity."] if is_customer_reported else ["Flagged by monitoring system."],
            },
            {
                "id": "hyp_2_unauthorized_fraud",
                "title": "Unauthorized Third-Party Fraud",
                "description": "Transaction was conducted by an unauthorized third party using compromised credentials.",
                "confidence": 0.80 if is_customer_reported else 0.45,
                "supporting_evidence": ["Customer filed report indicating unfamiliar charge."] if is_customer_reported else [f"Transaction {flagged_txn_id} flagged for review."],
                "contradicting_evidence": [] if is_customer_reported else ["Customer relationship exists with historical activity."],
            },
            {
                "id": "hyp_3_coordinated_or_uncertain",
                "title": "Unconfirmed Authorization / Potential Coordinated Pattern",
                "description": "Evidence is incomplete or exhibits multi-entity coordination requiring cardholder verification outreach.",
                "confidence": 0.60,
                "supporting_evidence": ["Cardholder direct outreach pending; authorization status unverified."],
                "contradicting_evidence": [],
            },
        ]

    def _build_case_context(self, state: dict[str, Any]) -> str:
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

        return f"""CASE INFORMATION:

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

TOOLS USED SO FAR:
{state.get("tools_used", [])}

Investigate this case. Choose the appropriate investigation tools to execute, or conclude if enough evidence has been gathered.
"""