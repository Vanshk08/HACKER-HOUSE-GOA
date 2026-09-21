"""
Policy Agent for the fraud investigation system.
StateGraph node that evaluates deterministic policy rules (R1-R10) on the completed
investigation and assessment, producing structured PolicyDecision.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. The Policy Agent MUST NOT have investigation tools.
2. The Policy Agent must NOT call get_transaction, get_customer_history, get_card_history, etc.
3. All investigation must already be finished before Policy runs.
4. Policy rules R1-R10 are evaluated deterministically; the LLM does NOT decide rules or actions.
5. If an LLM is optionally configured, it may ONLY summarize or explain the already-decided outcome.
"""

from typing import Any
from langchain_core.messages import AIMessage

try:
    from config.policy import evaluate_policy
    from schemas.decision import PolicyDecision
except ImportError:
    from ..config.policy import evaluate_policy
    from ..schemas.decision import PolicyDecision


class PolicyAgent:
    """
    Policy Agent that applies deterministic R1-R10 rules to the investigation
    findings and Assessment, outputting the final policy decisions and actions.
    """

    def __init__(self, llm=None):
        # The Policy Agent has NO investigation tools.
        self.llm = llm

    def node(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        StateGraph node function.
        Receives the completed investigation + assessment and executes deterministic policy rules.
        """
        # Deterministically evaluate policy rules
        decision: PolicyDecision = evaluate_policy(state)

        # Build update dict for InvestigationState
        updates: dict[str, Any] = {
            "policy_decision": decision,
            "actions": decision.get("actions", []),
        }
        if decision.get("evidence_requests"):
            updates["evidence_requests"] = decision["evidence_requests"]

        # If an LLM is provided, use it strictly to generate a human-readable summary/explanation
        # of the already-determined policy decision (never to pick or alter actions).
        if self.llm is not None:
            prompt = (
                f"Explain the following deterministic fraud policy decision for case {state.get('case_id')}:\n"
                f"Matched Rules: {decision.get('matched_rules')}\n"
                f"Actions: {decision.get('actions')}\n"
                f"Primary Action: {decision.get('primary_action')}\n"
                f"Exposure: ${decision.get('exposure'):.2f}\n"
                f"Rationale: {decision.get('rationale')}\n"
            )
            try:
                explanation = self.llm.invoke(prompt)
                explanation_text = explanation.content if hasattr(explanation, "content") else str(explanation)
                # Append explanation to messages history
                messages = list(state.get("messages", []))
                messages.append(AIMessage(content=f"POLICY DECISION EXPLANATION:\n{explanation_text}"))
                updates["messages"] = messages
            except Exception:
                # Deterministic decision remains unaffected by LLM explanation failures
                pass

        return updates
