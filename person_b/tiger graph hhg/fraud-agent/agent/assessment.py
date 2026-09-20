"""
Assessment Agent for evaluating evidence gathered during fraud investigation.
"""

import json
from typing import Any, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

try:
    from investigation.assessment import Assessment, VerdictType
except ImportError:
    from agent.state import Assessment
    VerdictType = Literal["confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"]


ASSESSMENT_SYSTEM_PROMPT = """You are the Assessment Agent in a financial fraud investigation system.

Your job is to critically evaluate the evidence gathered during the investigation
and determine a structured fraud assessment.

You are an EVALUATOR, not an investigator and not a policy decision maker.
You do NOT execute investigation tools, and you do NOT make policy decisions
(do NOT output actions like BLOCK_CARD, FILE_REPORT, ESCALATE, CLOSE_CASE, etc.
Policy decisions will be handled by a separate downstream Policy Agent).

CRITICAL EVALUATION PRINCIPLES:
1. EVIDENCE-BASED REASONING:
   Base your assessment strictly on the concrete evidence collected.
   Never invent IDs, card numbers, transaction amounts, exposure values, or evidence.
   If data was not observed or is marked unavailable, acknowledge it as missing.

2. COMPETING EXPLANATIONS:
   Rigorously evaluate both fraudulent and legitimate explanations.
   Actively identify contradicting evidence (evidence inconsistent with fraud)
   as well as supporting evidence.

3. CONTEXTUAL USE OF CLOSED CASES:
   Historical closed cases (from July–October) provide context, behavioral precedents,
   and pattern similarity.
   NEVER treat a similar closed case as direct proof that the current case is fraud.

4. RISK SCORE vs FRAUD ASSESSMENT:
   The original case-pack risk_score is only the reason the case was flagged for review.
   It is NOT a fraud verdict. Your fraud_probability must be an independent,
   evidence-based assessment derived from the investigation findings, NOT a copy
   or calibration of the original risk score.

5. EXPLICIT UNCERTAINTY:
   When decision-relevant evidence is incomplete, ambiguous, or contradictory,
   you MUST select the verdict 'uncertain' and clearly explain what information
   is missing. Do not force a fraud or legitimate verdict without sufficient evidence.

6. NO POLICY ACTIONS:
   Do not decide what action to take (e.g. blocking cards or filing reports).
   Confine your output strictly to the assessment of fraud likelihood, type, exposure,
   evidence, and reasoning.

VERDICT DEFINITIONS:
- 'confirmed_fraud': Concrete, conclusive evidence demonstrates unauthorized or fraudulent activity.
- 'suspected_fraud': Strong indicators of fraud exist, but some uncertainty or missing data prevents absolute confirmation.
- 'uncertain': Evidence is conflicting, inconclusive, or insufficient to distinguish legitimate from fraudulent activity.
- 'legitimate': Evidence demonstrates authorized activity consistent with normal customer behavior.
"""


class AssessmentSchema(BaseModel):
    verdict: VerdictType = Field(
        description="Verdict: 'confirmed_fraud', 'suspected_fraud', 'uncertain', or 'legitimate'."
    )
    fraud_probability: float = Field(
        description="Evidence-based fraud probability between 0.0 and 1.0 derived from gathered investigation evidence. Not the original risk score.",
        ge=0.0,
        le=1.0,
    )
    fraud_type: str | None = Field(
        default=None,
        description="Specific category of fraud if applicable (e.g., 'account_takeover', 'card_cloning', 'identity_theft', 'friendly_fraud', 'credential_stuffing', or None).",
    )
    exposure: float = Field(
        default=0.0,
        description="Known monetary amount at risk or flagged transaction exposure. Never invent amounts.",
        ge=0.0,
    )
    affected_txn_ids: list[str] = Field(
        default_factory=list,
        description="List of verified affected transaction IDs. Do not invent transaction IDs.",
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Specific observations and evidence items supporting the verdict.",
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list,
        description="Specific observations contradicting fraud or supporting legitimate customer activity.",
    )
    reasoning: str = Field(
        description="Comprehensive evaluation explaining how the evidence led to this verdict, evaluating competing explanations and addressing uncertainty."
    )
    confidence: float = Field(
        description="Confidence level in this assessment between 0.0 and 1.0.",
        ge=0.0,
        le=1.0,
    )


class AssessmentAgent:
    """
    Evaluates evidence gathered by the Investigator and produces a structured Assessment.
    Does not execute tools or make policy decisions.
    """

    def __init__(self, llm):
        self.llm = llm
        self.structured_llm = None
        if hasattr(llm, "with_structured_output"):
            try:
                self.structured_llm = llm.with_structured_output(AssessmentSchema)
            except Exception:
                self.structured_llm = None

    def node(self, state: dict) -> dict:
        """
        LangGraph node execution. Evaluates investigation findings and returns
        the updated state with a structured Assessment.
        """
        context = self._build_assessment_context(state)
        messages = [
            SystemMessage(content=ASSESSMENT_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ]

        if self.structured_llm is not None:
            raw_output = self.structured_llm.invoke(messages)
            assessment_dict = self._normalize_assessment(raw_output, state)
        else:
            raw_output = self.llm.invoke(messages)
            assessment_dict = self._normalize_assessment(raw_output, state)

        return {
            "assessment": assessment_dict,
        }

    def _build_assessment_context(self, state: dict) -> str:
        messages = state.get("messages", [])
        investigator_response = state.get("investigator_response", "")
        if not investigator_response and messages:
            for m in reversed(messages):
                if getattr(m, "type", None) == "ai" or type(m).__name__ == "AIMessage":
                    if not getattr(m, "tool_calls", None):
                        investigator_response = getattr(m, "content", "")
                        break
            if not investigator_response and messages:
                investigator_response = getattr(messages[-1], "content", "")

        evidence = state.get("evidence", [])
        hypotheses = state.get("hypotheses", [])
        evidence_requests = state.get("evidence_requests", [])
        tools_used = state.get("tools_used", [])

        trigger_type = state.get("trigger_type")
        trigger_text = state.get("trigger_text")
        risk_score = state.get("risk_score")
        customer_status = state.get("customer_response_status")
        trigger_info = ""
        if trigger_type:
            trigger_info += f"- trigger_type: {trigger_type}\n"
        if trigger_text:
            trigger_info += f"- trigger_text: {trigger_text}\n"
        if risk_score is not None:
            trigger_info += f"- risk_score: {risk_score}\n"
        if customer_status:
            trigger_info += f"- customer_response_status: {customer_status}\n"

        return f"""CASE INFORMATION:
- case_id: {state.get("case_id")}
- customer_id: {state.get("customer_id")}
- card_id: {state.get("card_id")}
- flagged_txn_id: {state.get("flagged_txn_id")}
{trigger_info}
INVESTIGATOR'S FINAL SYNTHESIS:
{investigator_response}

EVIDENCE GATHERED ({len(evidence)} items):
{evidence}

WORKING HYPOTHESES:
{hypotheses}

OUTSTANDING EVIDENCE REQUESTS:
{evidence_requests}

TOOLS USED DURING INVESTIGATION:
{tools_used}

Evaluate all gathered evidence and produce the structured Assessment."""

    def _normalize_assessment(self, raw_output: Any, state: dict) -> Assessment:
        data: dict[str, Any] = {}

        if hasattr(raw_output, "content"):
            content = raw_output.content
            if isinstance(content, str):
                content = content.strip()
                if content.startswith("```"):
                    lines = content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    content = "\n".join(lines).strip()
                try:
                    data = json.loads(content)
                except Exception:
                    data = {
                        "verdict": "uncertain",
                        "reasoning": content,
                    }
            elif isinstance(content, dict):
                data = content
        elif hasattr(raw_output, "model_dump"):
            data = raw_output.model_dump()
        elif isinstance(raw_output, dict):
            data = raw_output
        elif isinstance(raw_output, str):
            try:
                data = json.loads(raw_output)
            except Exception:
                data = {
                    "verdict": "uncertain",
                    "reasoning": raw_output,
                }

        verdict_str = str(data.get("verdict", "uncertain")).strip().lower()
        if verdict_str in ("confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"):
            verdict: VerdictType = verdict_str  # type: ignore
        else:
            verdict = "uncertain"

        try:
            fraud_prob = float(
                data.get(
                    "fraud_probability",
                    0.5 if verdict == "uncertain" else (0.9 if verdict == "confirmed_fraud" else (0.7 if verdict == "suspected_fraud" else 0.1)),
                )
            )
            fraud_prob = max(0.0, min(1.0, fraud_prob))
        except (ValueError, TypeError):
            fraud_prob = 0.5

        fraud_type = data.get("fraud_type")
        if fraud_type is not None:
            fraud_type = str(fraud_type)

        try:
            exposure = float(data.get("exposure", 0.0))
            exposure = max(0.0, exposure)
        except (ValueError, TypeError):
            exposure = 0.0

        raw_affected = data.get("affected_txn_ids", [])
        if isinstance(raw_affected, list):
            affected_txn_ids = [str(x) for x in raw_affected]
        elif raw_affected:
            affected_txn_ids = [str(raw_affected)]
        else:
            affected_txn_ids = []

        raw_supporting = data.get("supporting_evidence", [])
        if isinstance(raw_supporting, list):
            supporting_evidence = [str(x) for x in raw_supporting]
        elif raw_supporting:
            supporting_evidence = [str(raw_supporting)]
        else:
            supporting_evidence = []

        raw_contradicting = data.get("contradicting_evidence", [])
        if isinstance(raw_contradicting, list):
            contradicting_evidence = [str(x) for x in raw_contradicting]
        elif raw_contradicting:
            contradicting_evidence = [str(raw_contradicting)]
        else:
            contradicting_evidence = []

        reasoning = str(data.get("reasoning", "Assessment concluded based on gathered investigation evidence."))

        try:
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5

        return {
            "verdict": verdict,
            "fraud_probability": fraud_prob,
            "fraud_type": fraud_type,
            "exposure": exposure,
            "affected_txn_ids": affected_txn_ids,
            "supporting_evidence": supporting_evidence,
            "contradicting_evidence": contradicting_evidence,
            "reasoning": reasoning,
            "confidence": confidence,
        }
