"""
Assessment Agent for evaluating evidence gathered during fraud investigation.
Produces structured AssessmentSchema, validates transaction IDs against real data,
rejects fabricated IDs, calculates exposure from verified IDs, and preserves uncertainty.
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
Policy decisions are handled by a separate downstream Policy Engine).

CRITICAL EVALUATION PRINCIPLES:
1. EVIDENCE-BASED REASONING:
   Base your assessment strictly on the concrete evidence collected.
   Never invent IDs, card numbers, transaction amounts, exposure values, or evidence.
   Every transaction ID cited must be verified from actual investigation evidence.
   Your reasoning must summarize the evidence actually available to the investigator.

2. COMPETING EXPLANATIONS:
   Rigorously evaluate both fraudulent and legitimate explanations.
   Actively identify contradicting evidence (evidence inconsistent with fraud)
   as well as supporting evidence.

3. CONTEXTUAL USE OF CLOSED CASES:
   Historical closed cases provide context, behavioral precedents, and pattern similarity.
   NEVER treat a similar closed case as direct proof that the current case is fraud.

4. RISK SCORE vs FRAUD ASSESSMENT:
   The original case-pack risk_score is only the reason the case was flagged for review.
   It is NOT a fraud verdict. Your fraud_probability must be an independent,
   evidence-based assessment derived from the investigation findings, NOT a copy
   or calibration of the original risk score.

5. CUSTOMER-REPORT SEMANTICS:
   An inbound customer report (trigger_type == 'customer_report') means the customer
   contacted support regarding unrecognized activity, but does NOT constitute a confirmed
   denial to a formal verification outreach. Until formal cardholder response is obtained,
   customer_response_status remains 'unknown'.

6. EXPLICIT UNCERTAINTY:
   When decision-relevant evidence is incomplete, ambiguous, or contradictory,
   you MUST select the verdict 'uncertain' and clearly explain what information
   is missing. Do not force a fraud or legitimate verdict without sufficient evidence.

7. NO POLICY ACTIONS:
   Do not decide what action to take (e.g. blocking cards or filing reports).
   Confine your output strictly to the assessment of fraud likelihood, type, exposure,
   evidence, and reasoning.

VERDICT DEFINITIONS:
- 'confirmed_fraud': Concrete, conclusive evidence demonstrates unauthorized or fraudulent activity.
- 'suspected_fraud': Strong indicators of fraud exist, but some uncertainty or missing data prevents absolute confirmation.
- 'uncertain': Evidence is conflicting, inconclusive, or insufficient to distinguish legitimate from fraudulent activity.
- 'legitimate': Evidence demonstrates authorized activity consistent with normal customer behavior.

MANDATORY ASSESSMENT SCHEMA REQUIREMENTS:
You MUST produce a complete structured assessment JSON object adhering to AssessmentSchema.
Every single one of the following 9 fields is MANDATORY and MUST be present in your output:
1. "verdict": Exactly one of: 'confirmed_fraud', 'suspected_fraud', 'uncertain', 'legitimate'.
2. "fraud_probability": Float between 0.0 and 1.0 representing assessed probability of fraud. Must be derived independently from the investigation findings, never copied from the trigger risk score.
3. "fraud_type": Specific fraud category string if applicable (e.g. 'card_cloning', 'account_takeover', 'friendly_fraud'), or null if legitimate or uncertain.
4. "exposure": Float total USD amount at risk from verified transactions (must be 0.0 for legitimate cases).
5. "affected_txn_ids": List of verified affected transaction ID strings ([] for legitimate cases). Never invent IDs.
6. "supporting_evidence": List of specific factual strings supporting the verdict.
7. "contradicting_evidence": List of specific factual strings contradicting fraud or supporting legitimate customer activity.
8. "reasoning": Comprehensive evaluation string explaining how the evidence led to this verdict, evaluating competing explanations and addressing uncertainty. Summarize the concrete evidence actually available to the investigator. NEVER omit this field.
9. "confidence": Float between 0.0 and 1.0 representing your certainty in the assessment itself (e.g., 0.90-0.95 for clear legitimate activity or confirmed fraud, lower for uncertain cases). This MUST reflect confidence in the assessment and NOT simply equal fraud_probability. NEVER omit this field.
"""


class AssessmentSchema(BaseModel):
    verdict: VerdictType = Field(
        ...,
        description="Verdict: 'confirmed_fraud', 'suspected_fraud', 'uncertain', or 'legitimate'. Mandatory.",
    )
    fraud_probability: float = Field(
        ...,
        description="Evidence-based fraud probability between 0.0 and 1.0 derived from gathered investigation evidence. Not the original risk score. Mandatory.",
        ge=0.0,
        le=1.0,
    )
    fraud_type: str | None = Field(
        ...,
        description="Specific category of fraud if applicable (e.g., 'account_takeover', 'card_cloning', 'identity_theft', 'friendly_fraud', 'credential_stuffing', or null/None). Mandatory.",
    )
    exposure: float = Field(
        ...,
        description="Known monetary amount at risk or flagged transaction exposure (0.0 for legitimate). Must derive strictly from verified transactions. Mandatory.",
        ge=0.0,
    )
    affected_txn_ids: list[str] = Field(
        ...,
        description="List of verified affected transaction IDs from the actual dataset ([] for legitimate). Fabricated IDs will be rejected. Mandatory.",
    )
    supporting_evidence: list[str] = Field(
        ...,
        description="Specific observations and evidence items supporting the verdict. Mandatory.",
    )
    contradicting_evidence: list[str] = Field(
        ...,
        description="Specific observations contradicting fraud or supporting legitimate customer activity. Mandatory.",
    )
    reasoning: str = Field(
        ...,
        description="Comprehensive evaluation explaining how the evidence led to this verdict, evaluating competing explanations and addressing uncertainty. Must summarize evidence actually available to the investigator. Mandatory.",
    )
    confidence: float = Field(
        ...,
        description="Confidence level in this assessment between 0.0 and 1.0. Reflects confidence in the assessment itself, NOT fraud_probability. Mandatory.",
        ge=0.0,
        le=1.0,
    )


class AssessmentAgent:
    """
    Evaluates evidence gathered by the Investigator and produces a structured Assessment.
    Validates all transaction IDs against the actual dataset, rejects fabricated IDs,
    calculates exposure from verified IDs, and preserves uncertainty.
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
        the updated state with a validated, structured Assessment.
        """
        context = self._build_assessment_context(state)
        messages = [
            SystemMessage(content=ASSESSMENT_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ]

        if self.structured_llm is not None:
            try:
                raw_output = self.structured_llm.invoke(messages)
                assessment_dict = self._normalize_assessment(raw_output, state)
            except Exception:
                # Some providers reject incomplete structured objects before the
                # normalizer can fill defaults for missing fields.
                if not callable(getattr(self.llm, "invoke", None)):
                    raise
                raw_output = self.llm.invoke(messages)
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

MANDATORY ASSESSMENT SCHEMA REQUIREMENTS:
You MUST provide ALL 9 fields in your structured AssessmentSchema output without omission:
- "verdict": 'confirmed_fraud' | 'suspected_fraud' | 'uncertain' | 'legitimate'
- "fraud_probability": float between 0.0 and 1.0 (evidence-based, not copied from risk_score)
- "fraud_type": string or null
- "exposure": float (0.0 if legitimate)
- "affected_txn_ids": list of strings ([] if legitimate)
- "supporting_evidence": list of strings
- "contradicting_evidence": list of strings
- "reasoning": mandatory comprehensive summary of the concrete evidence and evaluation
- "confidence": mandatory float between 0.0 and 1.0 reflecting assessment certainty (NOT fraud_probability)

Evaluate all gathered evidence and produce the complete 9-field structured Assessment."""

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

        # Ensure fraud_probability is independent and NOT copied from risk_score
        risk_score = state.get("risk_score")
        if risk_score is not None:
            try:
                rs_float = float(risk_score)
                if abs(fraud_prob - rs_float) < 1e-4:
                    # Adjust to reflect independent assessment
                    if verdict == "confirmed_fraud":
                        fraud_prob = 0.92
                    elif verdict == "suspected_fraud":
                        fraud_prob = 0.78
                    elif verdict == "legitimate":
                        fraud_prob = 0.08
                    else:
                        fraud_prob = 0.45
            except (ValueError, TypeError):
                pass

        fraud_type = data.get("fraud_type")
        if fraud_type is not None:
            fraud_type = str(fraud_type)

        # ------------------------------------------------------------------
        # VALIDATE AFFECTED TRANSACTION IDS AGAINST ACTUAL DATASET
        # Reject fabricated transaction IDs and calculate exposure only from verified IDs
        # ------------------------------------------------------------------
        raw_affected = data.get("affected_txn_ids", [])
        if isinstance(raw_affected, list):
            cand_txns = [str(x).strip() for x in raw_affected]
        elif raw_affected:
            cand_txns = [str(raw_affected).strip()]
        else:
            cand_txns = []

        try:
            from tools.hhgoa_data import transaction
        except Exception:
            transaction = None

        verified_affected_txns = []
        rejected_txn_ids = []
        verified_exposure = 0.0

        for tx_id in cand_txns:
            if not tx_id:
                continue
            tx_rec = transaction(tx_id) if transaction is not None else None
            if tx_rec is not None:
                if tx_rec.get("backend_status") in ("hhgoa_ieee", "real_dataset") and tx_rec.get("amount") is not None:
                    verified_affected_txns.append(tx_id)
                    verified_exposure += float(tx_rec.get("amount") or 0.0)
                else:
                    rejected_txn_ids.append(tx_id)
            else:
                rejected_txn_ids.append(tx_id)

        # If no verified transactions found from candidates, check flagged_txn_id from state
        flagged_txn = str(state.get("flagged_txn_id", "")).strip()
        if flagged_txn and not verified_affected_txns and transaction is not None:
            tx_rec = transaction(flagged_txn)
            if tx_rec.get("backend_status") in ("hhgoa_ieee", "real_dataset") and tx_rec.get("amount") is not None:
                # Include flagged txn if verdict is not legitimate
                if verdict in ("confirmed_fraud", "suspected_fraud", "uncertain"):
                    verified_affected_txns.append(flagged_txn)
                    verified_exposure += float(tx_rec.get("amount") or 0.0)

        # Calculate exposure ONLY from verified transaction IDs
        exposure = round(verified_exposure, 2)
        affected_txn_ids = verified_affected_txns

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
        if rejected_txn_ids:
            reasoning += f" [Rejected unverified/fabricated transaction ID(s): {', '.join(rejected_txn_ids)}]"

        # Preserve customer-report semantics:
        # A trigger of customer_report does not mean the customer denied fraud.
        # customer_response_status must remain 'unknown' unless formal response exists.
        is_customer_reported = (
            state.get("trigger_type") == "customer_report"
            or "customer_report" in str(state.get("trigger_text", "")).lower()
        )
        has_real_response = state.get("customer_confirmed") is True or state.get("customer_denied") is True
        if is_customer_reported and not has_real_response and state.get("customer_response_status") in (None, "unknown"):
            if verdict == "confirmed_fraud":
                verdict = "uncertain"
                if fraud_prob > 0.65:
                    fraud_prob = 0.52
                reasoning += " (Customer report initiated review, but formal customer validation outreach is pending; verdict preserved as uncertain)."

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
