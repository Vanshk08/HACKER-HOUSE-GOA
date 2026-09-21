"""
Deterministic Policy Engine for the fraud investigation system.
Implements the challenge rules R1 through R10, global CREATE_CASE and FILE_REPORT requirements,
and provides a deterministic evaluator.
"""

from dataclasses import dataclass, field
from typing import Any

try:
    from schemas.decision import (
        ActionType,
        CustomerResponseStatusType,
        VALID_ACTIONS,
        PolicyDecision,
    )
except ImportError:
    from ..schemas.decision import (
        ActionType,
        CustomerResponseStatusType,
        VALID_ACTIONS,
        PolicyDecision,
    )


# Priority hierarchy for selecting the primary operational action
ACTION_PRIORITY: list[ActionType] = [
    "BLOCK_CARD",
    "FILE_REPORT",
    "ESCALATE_TO_ANALYST",
    "DECLINE_TRANSACTION",
    "STEP_UP_AUTH",
    "VERIFY_WITH_CUSTOMER",
    "WARN_CUSTOMER",
    "MONITOR_CONNECTED_CARDS",
    "MONITOR_CARD",
    "CREATE_CASE",
    "CLOSE_NO_FRAUD",
]


@dataclass
class RuleResult:
    """Outcome of evaluating an individual policy rule."""
    rule_id: str
    name: str
    matched: bool
    actions: list[ActionType]
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


def determine_single_signal(context: dict[str, Any]) -> bool:
    """
    Deterministically evaluates whether the case rests on a single decision-relevant signal.

    A case is treated as single-signal when the decision is materially supported only
    by one signal, including:
    - risk score alone
    - customer dispute alone
    - single device or single pattern signal without independent corroboration

    A case is treated as NOT single-signal when:
    - multiple independent corroborating sources support the assessment
    - multiple independent fraud pattern/cluster signals are active
    - the assessment verdict is legitimate with corroborating evidence
    """
    # 1. Direct explicit overrides
    if context.get("is_single_signal") is not None:
        return bool(context["is_single_signal"])
    if context.get("rests_on_single_signal") is not None:
        return bool(context["rests_on_single_signal"])
    if context.get("single_signal") is not None:
        return bool(context["single_signal"])

    # 2. Explicit multiple corroborating sources flags
    if (
        context.get("has_multiple_corroborating_sources") is True
        or context.get("multiple_corroborating_sources") is True
        or context.get("multiple_independent_evidence_sources") is True
    ):
        return False

    # 3. Explicit collections of independent / corroborating sources
    for key in (
        "independent_evidence_sources",
        "evidence_sources",
        "corroborating_sources",
        "corroborating_evidence",
    ):
        val = context.get(key)
        if val is not None:
            if isinstance(val, (list, tuple, set)):
                if len(val) > 1:
                    return False
                elif len(val) == 1:
                    return True
            elif isinstance(val, (int, float)):
                if val > 1:
                    return False
                elif val == 1:
                    return True

    # 4. Check assessment for legitimate verdict with corroborating evidence
    verdict = context.get("verdict")
    if verdict == "legitimate":
        # Legitimate verdict supported by multiple contradicting/supporting evidence items
        # or clearing fraud suspicion does not rest on a single fraud signal
        return False

    # 5. Count active independent fraud / risk signals
    active_signals: list[str] = []

    # Signal 1: Risk score (alone or elevated)
    risk_score = context.get("risk_score")
    trigger_type = context.get("trigger_type")
    if (risk_score is not None and float(risk_score) > 0.0) or trigger_type == "risk_score":
        active_signals.append("risk_score")

    # Signal 2: Customer dispute / report
    if context.get("is_customer_dispute") or trigger_type == "customer_report":
        active_signals.append("customer_dispute")

    # Signal 3: Analyst alert / request
    if trigger_type in ("analyst_alert", "analyst_request"):
        active_signals.append("analyst_alert")

    # Signal 4: Card testing pattern
    if context.get("has_card_testing_pattern"):
        active_signals.append("card_testing")

    # Signal 5: Shared device fraud cluster
    if context.get("has_shared_device_fraud_cluster"):
        active_signals.append("shared_device_cluster")

    # Signal 6: Shared region fraud cluster
    if context.get("has_shared_region_fraud_cluster"):
        active_signals.append("shared_region_cluster")

    # Signal 7: Connected to another customer's fraud
    if context.get("has_other_customer_fraud"):
        active_signals.append("other_customer_fraud")

    # Signal 8: Another card fraud established
    if context.get("has_another_card_fraud"):
        active_signals.append("another_card_fraud")

    # Signal 9: Undocumented coordinated abuse
    if context.get("has_undocumented_abuse"):
        active_signals.append("undocumented_abuse")

    # Multiple active signals mean multiple corroborating sources -> NOT single signal
    if len(active_signals) > 1:
        return False

    # Exactly 1 active signal -> rests on single signal
    if len(active_signals) == 1:
        return True

    # When 0 explicit signal flags were set, but case is uncertain unconfirmed risk:
    # it rests on the single unconfirmed trigger
    if verdict == "uncertain":
        return True

    return False


def extract_policy_context(state: dict[str, Any]) -> dict[str, Any]:
    """
    Extracts structured operational context from InvestigationState,
    Assessment, Evidence, Hypotheses, and EvidenceRequests.
    """
    assessment = state.get("assessment") or {}
    evidence = state.get("evidence") or []
    hypotheses = state.get("hypotheses") or []
    evidence_requests = state.get("evidence_requests") or []
    supporting_evidence = assessment.get("supporting_evidence") or state.get("supporting_evidence") or []
    contradicting_evidence = assessment.get("contradicting_evidence") or state.get("contradicting_evidence") or []

    # Assessment fields
    verdict = assessment.get("verdict", "uncertain")
    fraud_probability = float(assessment.get("fraud_probability", 0.0))
    exposure = float(assessment.get("exposure", 0.0))
    affected_txn_ids = list(assessment.get("affected_txn_ids") or [])

    # If exposure was 0.0 but flagged_txn_id exists in evidence, inspect evidence (unless legitimate)
    if verdict == "legitimate":
        exposure = 0.0
        affected_txn_ids = []
    elif exposure == 0.0 and state.get("flagged_txn_id"):
        for ev in evidence:
            if ev.get("source") == "get_transaction":
                res = ev.get("data", {}).get("result", {})
                if str(res.get("transaction_id")) == str(state.get("flagged_txn_id")):
                    exposure = float(res.get("amount", 0.0))
                    if not affected_txn_ids:
                        affected_txn_ids = [str(state.get("flagged_txn_id"))]
                    break

    # Determine channel
    channel = state.get("channel")
    if not channel:
        for ev in evidence:
            if ev.get("source") == "get_transaction":
                channel = ev.get("data", {}).get("result", {}).get("channel")
                break
    if not channel:
        channel = "in_person" if state.get("card_present", False) else "unknown"

    # Determine customer response status
    # Strictly distinguish 'unknown' from 'confirmed', 'denied', or 'no_response'
    customer_response_status = state.get("customer_response_status")
    if not customer_response_status:
        if state.get("customer_confirmed") is True:
            customer_response_status = "confirmed"
        elif state.get("customer_denied") is True:
            customer_response_status = "denied"
        elif state.get("no_response_24h") is True or (state.get("hours_since_outreach", 0) >= 24.0):
            customer_response_status = "no_response"
        else:
            # Check evidence_requests: pending requests mean response is unknown
            customer_response_status = "unknown"

    # If legitimate verdict but customer has not confirmed, ensure customer confirmation request is recorded
    # rather than silently closing the case
    if verdict == "legitimate" and customer_response_status != "confirmed":
        flagged_txn = str(state.get("flagged_txn_id") or "")
        has_cust_req = any(
            isinstance(r, dict) and r.get("request_type") == "customer_confirmation"
            for r in evidence_requests
        )
        if not has_cust_req and flagged_txn:
            from datetime import datetime, timezone
            evidence_requests = list(evidence_requests) + [{
                "request_id": f"req_cust_{flagged_txn}",
                "request_type": "customer_confirmation",
                "transaction_id": flagged_txn,
                "question": f"Did you authorize transaction {flagged_txn}?",
                "status": "pending",
                "customer_response_status": customer_response_status,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "channel": "customer_outreach",
                    "awaiting_response": True,
                    "customer_response_status": customer_response_status,
                    "reason": "Policy requires customer confirmation before closing legitimate case.",
                },
            }]

    # Determine hours since outreach
    hours_since_outreach = state.get("hours_since_outreach")
    if hours_since_outreach is None and state.get("no_response_24h") is True:
        hours_since_outreach = 24.0

    # Pattern and graph flags
    has_card_testing_pattern = bool(state.get("card_testing_detected", False))
    cleared_amount_card_testing = float(state.get("cleared_amount_card_testing", 0.0))

    has_shared_device_fraud_cluster = bool(state.get("shared_device_fraud_cluster", False))
    has_shared_region_fraud_cluster = bool(state.get("shared_region_fraud_cluster", False))
    has_other_customer_fraud = bool(state.get("other_customer_fraud", False))
    has_another_card_fraud = bool(state.get("another_card_fraud_established", False))
    has_undocumented_abuse = bool(state.get("undocumented_coordinated_abuse", False))

    is_disputed_legitimate_recurring = bool(state.get("disputed_legitimate_recurring", False))
    conflicting_evidence_requiring_analyst = bool(state.get("requires_analyst_review", False))

    confirmed_compromised_cards_count = int(state.get("confirmed_compromised_cards_count", 0))
    credentials_confirmed_compromised = bool(state.get("credentials_confirmed_compromised", False))

    context = {
        "case_id": state.get("case_id"),
        "customer_id": state.get("customer_id"),
        "card_id": state.get("card_id"),
        "flagged_txn_id": state.get("flagged_txn_id"),
        "trigger_type": state.get("trigger_type"),
        "trigger_text": state.get("trigger_text"),
        "verdict": verdict,
        "fraud_probability": fraud_probability,
        "exposure": exposure,
        "affected_txn_ids": affected_txn_ids,
        "channel": channel,
        "customer_response_status": customer_response_status,
        "hours_since_outreach": hours_since_outreach,
        "evidence_requests": evidence_requests,
        "supporting_evidence": supporting_evidence,
        "contradicting_evidence": contradicting_evidence,
        "has_card_testing_pattern": has_card_testing_pattern,
        "cleared_amount_card_testing": cleared_amount_card_testing,
        "has_shared_device_fraud_cluster": has_shared_device_fraud_cluster,
        "has_shared_region_fraud_cluster": has_shared_region_fraud_cluster,
        "has_other_customer_fraud": has_other_customer_fraud,
        "has_another_card_fraud": has_another_card_fraud,
        "has_undocumented_abuse": has_undocumented_abuse,
        "is_disputed_legitimate_recurring": is_disputed_legitimate_recurring,
        "is_customer_dispute": bool(state.get("customer_dispute") or state.get("trigger_type") == "customer_report" or (state.get("trigger_text") and "never made this" in str(state.get("trigger_text", "")).lower())),
        "conflicting_evidence_requiring_analyst": conflicting_evidence_requiring_analyst,
        "confirmed_compromised_cards_count": confirmed_compromised_cards_count,
        "credentials_confirmed_compromised": credentials_confirmed_compromised,
        "risk_score": float(state.get("risk_score") or 0.0) if state.get("risk_score") is not None else 0.0,
        "hypotheses": hypotheses,
        "evidence": evidence,
        "independent_evidence_sources": state.get("independent_evidence_sources"),
        "has_multiple_corroborating_sources": state.get("has_multiple_corroborating_sources"),
    }

    # Deterministic single-signal context field
    is_single_signal = determine_single_signal(context)
    context["is_single_signal"] = is_single_signal
    context["rests_on_single_signal"] = is_single_signal

    return context


# ======================================================================
# INDIVIDUAL RULE IMPLEMENTATIONS (R1 - R10)
# ======================================================================

def rule_r1(context: dict[str, Any]) -> RuleResult:
    """
    R1: Weak single signal, including risk score alone, AND fraud probability < 0.70.
    -> VERIFY_WITH_CUSTOMER or STEP_UP_AUTH.
    Do NOT block the card based only on this evidence.
    """
    prob = float(context.get("fraud_probability", 0.0))
    verdict = context.get("verdict")
    status = context.get("customer_response_status")
    channel = context.get("channel")

    is_single_sig = context.get("is_single_signal")
    if is_single_sig is None:
        is_single_sig = context.get("rests_on_single_signal")
    if is_single_sig is None:
        is_single_sig = determine_single_signal(context)

    # Applies when resting on a single signal, fraud probability < 0.70, not confirmed/legitimate fraud,
    # and customer hasn't confirmed/denied yet
    if (
        is_single_sig
        and prob < 0.70
        and verdict not in ("confirmed_fraud", "legitimate")
        and status not in ("confirmed", "denied")
    ):
        # Select between VERIFY_WITH_CUSTOMER and STEP_UP_AUTH
        # For online transactions, STEP_UP_AUTH can be used; for in_person or external validation, VERIFY_WITH_CUSTOMER
        action: ActionType = "STEP_UP_AUTH" if channel == "online" else "VERIFY_WITH_CUSTOMER"
        return RuleResult(
            rule_id="R1",
            name="Weak Single Signal / Unconfirmed Risk",
            matched=True,
            actions=[action],
            rationale=(
                f"Weak single signal (fraud probability {prob:.2f} < 0.70). "
                f"Selected {action} without blocking card."
            ),
        )

    reasons = []
    if not is_single_sig:
        reasons.append("case does not rest on a single signal")
    if prob >= 0.70:
        reasons.append(f"fraud probability ({prob:.2f} >= 0.70)")
    if verdict == "confirmed_fraud":
        reasons.append("verdict is confirmed fraud")
    if verdict == "legitimate":
        reasons.append("verdict is legitimate")
    if status in ("confirmed", "denied"):
        reasons.append(f"customer response already resolved ('{status}')")

    return RuleResult(
        rule_id="R1",
        name="Weak Single Signal / Unconfirmed Risk",
        matched=False,
        actions=[],
        rationale="Condition not met: " + (", ".join(reasons) if reasons else "thresholds not satisfied") + ".",
    )


def rule_r2(context: dict[str, Any]) -> RuleResult:
    """
    R2: Customer denies the transaction:
    -> BLOCK_CARD
    -> CREATE_CASE
    Additionally:
    -> FILE_REPORT if exposure > $1,000 OR shared device profile exists OR another card's fraud is established.
    Do NOT add FILE_REPORT merely because customer denied.
    """
    status = context.get("customer_response_status")
    if status == "denied":
        actions: list[ActionType] = ["BLOCK_CARD", "CREATE_CASE"]
        exposure = context.get("exposure", 0.0)
        has_shared_device = context.get("has_shared_device_fraud_cluster", False)
        has_another_card_fraud = context.get("has_another_card_fraud", False)

        additional_reasons = []
        if exposure > 1000.0:
            additional_reasons.append(f"exposure (${exposure:.2f} > $1,000)")
        if has_shared_device:
            additional_reasons.append("shared device profile fraud cluster exists")
        if has_another_card_fraud:
            additional_reasons.append("another card fraud is established")

        if additional_reasons:
            actions.append("FILE_REPORT")
            rationale = (
                f"Customer denied transaction. Blocked card and created case. "
                f"Filed regulatory report due to: {', '.join(additional_reasons)}."
            )
        else:
            rationale = (
                f"Customer denied transaction. Blocked card and created case. "
                f"Report not filed (exposure ${exposure:.2f} <= $1,000, no shared device cluster, no other card fraud)."
            )

        return RuleResult(
            rule_id="R2",
            name="Customer Denial",
            matched=True,
            actions=actions,
            rationale=rationale,
        )

    return RuleResult(
        rule_id="R2",
        name="Customer Denial",
        matched=False,
        actions=[],
        rationale="Customer did not deny transaction (status is not 'denied').",
    )


def rule_r3(context: dict[str, Any]) -> RuleResult:
    """
    R3: Customer confirms the transaction:
    -> CLOSE_NO_FRAUD
    Do not block the card.
    """
    status = context.get("customer_response_status")
    if status == "confirmed":
        return RuleResult(
            rule_id="R3",
            name="Customer Confirmation",
            matched=True,
            actions=["CLOSE_NO_FRAUD"],
            rationale="Customer confirmed the transaction was authorized. Closed case with no fraud. Card remains active.",
        )

    return RuleResult(
        rule_id="R3",
        name="Customer Confirmation",
        matched=False,
        actions=[],
        rationale="Customer did not confirm transaction (status is not 'confirmed').",
    )


def rule_r4(context: dict[str, Any]) -> RuleResult:
    """
    R4: No customer response after 24 hours:
    -> MONITOR_CARD
    -> DECLINE_TRANSACTION for pending authorizations.
    If exposure > $500:
    -> ESCALATE_TO_ANALYST
    Do not assume no-response unless evidence actually establishes 24 hours have elapsed.
    """
    status = context.get("customer_response_status")
    hours = context.get("hours_since_outreach")

    # Strictly verify 24h elapsed or explicit no_response status
    is_24h_elapsed = (status == "no_response") or (hours is not None and hours >= 24.0)

    if is_24h_elapsed:
        actions: list[ActionType] = ["MONITOR_CARD", "DECLINE_TRANSACTION"]
        exposure = context.get("exposure", 0.0)
        if exposure > 500.0:
            actions.append("ESCALATE_TO_ANALYST")
            rationale = (
                f"No customer response after 24 hours. Monitored card, declined pending transaction, "
                f"and escalated to analyst due to exposure (${exposure:.2f} > $500)."
            )
        else:
            rationale = (
                f"No customer response after 24 hours. Monitored card and declined pending transaction. "
                f"Exposure (${exposure:.2f} <= $500) did not meet escalation threshold."
            )

        return RuleResult(
            rule_id="R4",
            name="No Customer Response After 24 Hours",
            matched=True,
            actions=actions,
            rationale=rationale,
        )

    return RuleResult(
        rule_id="R4",
        name="No Customer Response After 24 Hours",
        matched=False,
        actions=[],
        rationale="24 hours have not elapsed without customer response.",
    )


def rule_r5(context: dict[str, Any]) -> RuleResult:
    """
    R5: Card testing pattern:
    3 or more small online authorizations within 1 hour FOLLOWED BY a larger purchase
    -> DECLINE_TRANSACTION
    -> STEP_UP_AUTH
    If more than $100 was cleared:
    -> BLOCK_CARD
    """
    if context.get("has_card_testing_pattern"):
        actions: list[ActionType] = ["DECLINE_TRANSACTION", "STEP_UP_AUTH"]
        cleared = context.get("cleared_amount_card_testing", 0.0)
        if cleared > 100.0:
            actions.append("BLOCK_CARD")
            rationale = (
                f"Card testing sequence detected (3+ small authorizations within 1 hr followed by larger purchase). "
                f"Declined transaction, requested step-up auth, and blocked card (cleared amount ${cleared:.2f} > $100)."
            )
        else:
            rationale = (
                f"Card testing sequence detected. Declined transaction and requested step-up auth. "
                f"Card not blocked (cleared amount ${cleared:.2f} <= $100)."
            )

        return RuleResult(
            rule_id="R5",
            name="Card Testing Pattern",
            matched=True,
            actions=actions,
            rationale=rationale,
        )

    return RuleResult(
        rule_id="R5",
        name="Card Testing Pattern",
        matched=False,
        actions=[],
        rationale="Card testing pattern not detected in transaction sequence evidence.",
    )


def rule_r6(context: dict[str, Any]) -> RuleResult:
    """
    R6: Shared origin:
    Several cards show fraud from the same: device profile, billing region, or recipient email within one window.
    -> CREATE_CASE
    -> FILE_REPORT
    -> MONITOR_CONNECTED_CARDS for every card sharing the origin.
    Do NOT treat generic infrastructure such as Gmail or a common anonymized region as proof of coordinated fraud.
    """
    has_device_cluster = context.get("has_shared_device_fraud_cluster", False)
    has_region_cluster = context.get("has_shared_region_fraud_cluster", False)

    if has_device_cluster or has_region_cluster:
        reasons = []
        if has_device_cluster:
            reasons.append("shared device profile fraud cluster")
        if has_region_cluster:
            reasons.append("shared billing region fraud cluster")

        return RuleResult(
            rule_id="R6",
            name="Shared Origin Fraud Cluster",
            matched=True,
            actions=["CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS"],
            rationale=(
                f"Shared origin fraud cluster established via {', '.join(reasons)}. "
                f"Created case, filed report, and placed connected cards on monitoring."
            ),
        )

    return RuleResult(
        rule_id="R6",
        name="Shared Origin Fraud Cluster",
        matched=False,
        actions=[],
        rationale="No verified multi-card fraud cluster sharing origin entities.",
    )


def rule_r7(context: dict[str, Any]) -> RuleResult:
    """
    R7: Disputed but legitimate recurring pattern:
    -> CREATE_CASE
    -> VERIFY_WITH_CUSTOMER
    -> WARN_CUSTOMER
    Do NOT block.
    This requires evidence supporting the legitimate recurring pattern.
    """
    if context.get("is_disputed_legitimate_recurring"):
        return RuleResult(
            rule_id="R7",
            name="Disputed Legitimate Recurring Pattern",
            matched=True,
            actions=["CREATE_CASE", "VERIFY_WITH_CUSTOMER", "WARN_CUSTOMER"],
            rationale=(
                "Transaction flagged/disputed but strong evidence supports legitimate recurring spending pattern. "
                "Created case, initiated customer verification, and warned customer without blocking card."
            ),
        )

    return RuleResult(
        rule_id="R7",
        name="Disputed Legitimate Recurring Pattern",
        matched=False,
        actions=[],
        rationale="Conditions for disputed recurring legitimate pattern not met.",
    )


def rule_r8(context: dict[str, Any]) -> RuleResult:
    """
    R8: Uncertain AND:
    exposure > $500 OR conflicting evidence requiring analyst review:
    -> ESCALATE_TO_ANALYST
    Do not automatically escalate every uncertain case.
    """
    verdict = context.get("verdict")
    exposure = context.get("exposure", 0.0)
    conflicting = context.get("conflicting_evidence_requiring_analyst", False)

    if verdict == "uncertain" and (exposure > 500.0 or conflicting):
        reasons = []
        if exposure > 500.0:
            reasons.append(f"exposure (${exposure:.2f} > $500)")
        if conflicting:
            reasons.append("conflicting evidence requiring analyst review")

        return RuleResult(
            rule_id="R8",
            name="Uncertain High-Exposure / Conflicting Evidence",
            matched=True,
            actions=["ESCALATE_TO_ANALYST"],
            rationale=(
                f"Uncertain verdict with {', '.join(reasons)}. Escalated to analyst."
            ),
        )

    return RuleResult(
        rule_id="R8",
        name="Uncertain High-Exposure / Conflicting Evidence",
        matched=False,
        actions=[],
        rationale="Uncertain threshold not met (exposure <= $500 and no unresolved conflict requiring analyst review).",
    )


def rule_r9(context: dict[str, Any]) -> RuleResult:
    """
    R9: Undocumented coordinated/repeated abuse across customers:
    -> CREATE_CASE
    -> FILE_REPORT
    -> ESCALATE_TO_ANALYST
    The decision must describe the observed pattern. Do NOT force into known categories.
    """
    if context.get("has_undocumented_abuse"):
        return RuleResult(
            rule_id="R9",
            name="Undocumented Coordinated Abuse",
            matched=True,
            actions=["CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST"],
            rationale=(
                "Undocumented coordinated/repeated abuse pattern observed across customers. "
                "Created case, filed regulatory report, and escalated to fraud analyst."
            ),
        )

    return RuleResult(
        rule_id="R9",
        name="Undocumented Coordinated Abuse",
        matched=False,
        actions=[],
        rationale="No undocumented coordinated abuse pattern detected.",
    )


def rule_r10(context: dict[str, Any]) -> RuleResult:
    """
    R10: Guard rule: NEVER BLOCK_ALL_CARDS unless:
    at least two of the customer's cards are confirmed fraud
    OR credentials are confirmed compromised.
    """
    cards_count = context.get("confirmed_compromised_cards_count", 0)
    creds_compromised = context.get("credentials_confirmed_compromised", False)

    allowed = (cards_count >= 2) or creds_compromised
    return RuleResult(
        rule_id="R10",
        name="Block All Cards Guard",
        matched=True,
        actions=[],
        rationale=(
            "BLOCK_ALL_CARDS guard enforced: permitted only when 2+ cards confirmed fraud "
            "or credentials confirmed compromised."
        ),
        metadata={"allow_block_all_cards": allowed},
    )


# ======================================================================
# GLOBAL REQUIREMENT RULES
# ======================================================================

def rule_create_case(context: dict[str, Any]) -> RuleResult:
    """
    Global Requirement:
    CREATE_CASE whenever:
    - fraud probability >= 0.30 OR
    - evidence is requested OR
    - customer disputes the transaction
    """
    verdict = context.get("verdict")
    prob = context.get("fraud_probability", 0.0)
    has_requests = len(context.get("evidence_requests", [])) > 0
    is_disputed = (
        (context.get("customer_response_status") == "denied")
        or context.get("is_disputed_legitimate_recurring", False)
        or context.get("is_customer_dispute", False)
    )

    # For transactions assessed as legitimate without customer dispute, do not create a fraud case
    if verdict == "legitimate" and not is_disputed:
        return RuleResult(
            rule_id="GLOBAL_CREATE_CASE",
            name="Mandatory Case Creation",
            matched=False,
            actions=[],
            rationale="Case creation not triggered: transaction evaluated as legitimate without customer dispute.",
        )

    reasons = []
    if prob >= 0.30:
        reasons.append(f"fraud probability ({prob:.2f} >= 0.30)")
    if has_requests:
        reasons.append(f"external evidence requested ({len(context.get('evidence_requests', []))} pending request(s))")
    if is_disputed:
        reasons.append("customer disputed transaction")

    if reasons:
        return RuleResult(
            rule_id="GLOBAL_CREATE_CASE",
            name="Mandatory Case Creation",
            matched=True,
            actions=["CREATE_CASE"],
            rationale=f"Mandatory case creation triggered: {', '.join(reasons)}.",
        )

    return RuleResult(
        rule_id="GLOBAL_CREATE_CASE",
        name="Mandatory Case Creation",
        matched=False,
        actions=[],
        rationale="Case creation threshold not met (fraud probability < 0.30, no evidence requests, no customer dispute).",
    )


def rule_file_report(context: dict[str, Any]) -> RuleResult:
    """
    Global Requirement:
    FILE_REPORT when fraud is confirmed or strongly suspected AND:
    - exposure > $1,000 OR
    - shared device cluster OR
    - shared billing-region fraud cluster OR
    - another customer's fraud OR
    - coordinated/undocumented abuse pattern.
    """
    verdict = context.get("verdict")
    prob = context.get("fraud_probability", 0.0)
    is_strong_fraud = (verdict in ("confirmed_fraud", "suspected_fraud")) or (prob >= 0.70)

    if is_strong_fraud:
        exposure = context.get("exposure", 0.0)
        has_dev_cluster = context.get("has_shared_device_fraud_cluster", False)
        has_reg_cluster = context.get("has_shared_region_fraud_cluster", False)
        has_other_fraud = context.get("has_other_customer_fraud", False)
        has_abuse = context.get("has_undocumented_abuse", False)

        reasons = []
        if exposure > 1000.0:
            reasons.append(f"exposure (${exposure:.2f} > $1,000)")
        if has_dev_cluster:
            reasons.append("shared device fraud cluster")
        if has_reg_cluster:
            reasons.append("shared billing-region fraud cluster")
        if has_other_fraud:
            reasons.append("connected to another customer's confirmed fraud")
        if has_abuse:
            reasons.append("coordinated undocumented abuse pattern")

        if reasons:
            return RuleResult(
                rule_id="GLOBAL_FILE_REPORT",
                name="Mandatory Report Filing",
                matched=True,
                actions=["FILE_REPORT"],
                rationale=f"Mandatory regulatory report filing triggered: {', '.join(reasons)}.",
            )

    return RuleResult(
        rule_id="GLOBAL_FILE_REPORT",
        name="Mandatory Report Filing",
        matched=False,
        actions=[],
        rationale="Report filing conditions not met (requires confirmed/suspected fraud + escalation trigger).",
    )


# ======================================================================
# CENTRAL POLICY EVALUATOR
# ======================================================================

def evaluate_policy(state_or_context: dict[str, Any]) -> PolicyDecision:
    """
    Deterministically evaluates R1-R10 and global rules against the investigation context.

    Returns:
        Structured PolicyDecision adhering to the 10-field schema.
    """
    # Normalize input
    if "verdict" in state_or_context and "fraud_probability" in state_or_context:
        context = dict(state_or_context)
        if "is_single_signal" not in context and "rests_on_single_signal" not in context:
            is_single_sig = determine_single_signal(context)
            context["is_single_signal"] = is_single_sig
            context["rests_on_single_signal"] = is_single_sig
    else:
        context = extract_policy_context(state_or_context)

    matched_rules: list[str] = []
    rationales: list[str] = []
    candidate_actions: set[ActionType] = set()
    conflicts: list[str] = []

    # Run individual rules
    rule_evaluators = [
        rule_r1,
        rule_r2,
        rule_r3,
        rule_r4,
        rule_r5,
        rule_r6,
        rule_r7,
        rule_r8,
        rule_r9,
        rule_r10,
        rule_create_case,
        rule_file_report,
    ]

    r10_result = None
    for evaluator in rule_evaluators:
        res = evaluator(context)
        if res.rule_id == "R10":
            r10_result = res
        elif res.matched:
            matched_rules.append(res.rule_id)
            rationales.append(f"[{res.rule_id}] {res.rationale}")
            for act in res.actions:
                if act in VALID_ACTIONS:
                    candidate_actions.add(act)

    # ----------------------------------------------------
    # Policy Conflict Resolution & Guard Rails
    # ----------------------------------------------------

    # Conflict 1: Customer confirmed (CLOSE_NO_FRAUD) vs punitive actions (BLOCK_CARD, DECLINE_TRANSACTION)
    if "CLOSE_NO_FRAUD" in candidate_actions:
        punitive_actions = candidate_actions.intersection({"BLOCK_CARD", "DECLINE_TRANSACTION"})
        if punitive_actions:
            conflicts.append(
                f"Customer confirmed transaction, but punitive action(s) {punitive_actions} were candidate. "
                "Enforced customer confirmation: removed punitive actions."
            )
            candidate_actions.difference_update(punitive_actions)
        # If customer confirmed, do not verify again
        candidate_actions.discard("VERIFY_WITH_CUSTOMER")
        candidate_actions.discard("STEP_UP_AUTH")

    # Conflict 2: R10 Guard: Never BLOCK_ALL_CARDS unless 2+ cards confirmed fraud or credentials compromised
    if r10_result and not r10_result.metadata.get("allow_block_all_cards", False):
        if "BLOCK_ALL_CARDS" in candidate_actions:
            conflicts.append("R10 guard: stripped BLOCK_ALL_CARDS (insufficient confirmed compromised cards).")
            candidate_actions.discard("BLOCK_ALL_CARDS")

    # Conflict 3: If BLOCK_CARD is active, DECLINE_TRANSACTION is implicitly handled, but both may be kept
    # Keep valid operational actions sorted by defined priority
    sorted_actions = [a for a in ACTION_PRIORITY if a in candidate_actions]

    # Determine primary action
    primary_action = sorted_actions[0] if sorted_actions else None

    # Determine whether customer response is required
    requires_customer_response = bool(
        candidate_actions.intersection({"VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH"})
        or (context.get("customer_response_status") == "unknown" and len(context.get("evidence_requests", [])) > 0)
    )

    # Compile comprehensive rationale
    overall_rationale = (
        "Policy evaluation completed.\n" +
        "\n".join(rationales)
    )
    if conflicts:
        overall_rationale += "\nConflicts resolved:\n" + "\n".join(f"- {c}" for c in conflicts)

    decision: PolicyDecision = {
        "actions": sorted_actions,
        "primary_action": primary_action,
        "matched_rules": matched_rules,
        "rationale": overall_rationale,
        "requires_customer_response": requires_customer_response,
        "evidence_requests": context.get("evidence_requests", []),
        "exposure": 0.0 if context.get("verdict") == "legitimate" else float(context.get("exposure", 0.0)),
        "affected_txn_ids": [] if context.get("verdict") == "legitimate" else list(context.get("affected_txn_ids", [])),
        "customer_response_status": context.get("customer_response_status", "unknown"),
        "policy_conflicts": conflicts,
    }

    return decision
