"""
Output adapter for fraud investigation cases.
Serializes final case results to conform to the README output contract:
- case (with required case fields, exposure_usd, affected_txn_ids)
- evidence_requests (with customer response status & assumptions)
- next_best_actions (.initial and .final)
- sar (.file and .reasons)
- stop_reason
- tool_calls
- tokens
- latency
while preserving internal investigation/assessment/policy structures for backward compatibility.
"""

from typing import Any, Optional
from datetime import datetime, timezone


def compute_initial_actions(case_info: dict[str, Any], initial_state: Optional[dict[str, Any]] = None) -> list[str]:
    """
    Computes deterministic initial next-best-actions at case intake prior to deep investigation.
    Derived from the trigger type, initial risk score, and channel.
    """
    trigger_type = case_info.get("trigger_type") or (initial_state.get("trigger_type") if initial_state else None)
    risk_score = case_info.get("risk_score") if case_info.get("risk_score") is not None else (initial_state.get("risk_score") if initial_state else None)
    channel = case_info.get("channel") or (initial_state.get("channel") if initial_state else None)

    # Customer report / dispute trigger
    if trigger_type == "customer_report" or (case_info.get("trigger_text") and "never made" in str(case_info.get("trigger_text")).lower()):
        return ["VERIFY_WITH_CUSTOMER", "CREATE_CASE"]

    # Analyst alert / request trigger
    if trigger_type in ("analyst_alert", "analyst_request"):
        return ["ESCALATE_TO_ANALYST"]

    # Risk score trigger
    if trigger_type == "risk_score" or (risk_score is not None and float(risk_score) > 0.0):
        primary = "STEP_UP_AUTH" if channel == "online" else "VERIFY_WITH_CUSTOMER"
        actions = [primary]
        if risk_score is not None and float(risk_score) >= 0.30:
            actions.append("CREATE_CASE")
        return actions

    return ["VERIFY_WITH_CUSTOMER"]


def adapt_to_output_contract(
    case_info: dict[str, Any],
    final_state: dict[str, Any],
    elapsed_seconds: float = 0.0,
    provider_name: str = "mock",
    model_name: str = "unknown",
    initial_actions: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Adapts an investigation final state into the structured README-compliant output contract.

    Guarantees:
    - legitimate cases have affected_txn_ids = []
    - legitimate cases have exposure_usd = 0
    - legitimate cases have sar.file = false
    - initial and final next-best-actions are recorded
    - evidence requests and any simulated customer response/assumption are explicitly recorded
    - no action is invented merely because the verdict is legitimate.
    """
    case_id = str(case_info.get("case_id", final_state.get("case_id", "")))
    ass = final_state.get("assessment") or {}
    pol = final_state.get("policy_decision") or {}

    verdict = ass.get("verdict", "uncertain")
    fraud_prob = ass.get("fraud_probability")
    confidence = ass.get("confidence", 0.5)

    # 1. Exposure and Affected Transactions
    if verdict == "legitimate":
        exposure_usd = 0.0
        affected_txn_ids: list[str] = []
        fraud_type = None
    else:
        exposure_usd = round(float(ass.get("exposure", pol.get("exposure", 0.0))), 2)
        affected_txn_ids = list(ass.get("affected_txn_ids", pol.get("affected_txn_ids", [])))
        fraud_type = ass.get("fraud_type")

    # 2. Customer response status
    customer_response_status = (
        pol.get("customer_response_status")
        or final_state.get("customer_response_status")
        or "unknown"
    )

    # 3. Next-best-actions (initial and final)
    if initial_actions is None:
        initial_actions = compute_initial_actions(case_info, final_state)

    final_actions = list(pol.get("actions") or [])

    next_best_actions = {
        "initial": list(initial_actions),
        "final": list(final_actions),
    }

    # 4. Evidence Requests with customer response assumptions recorded
    raw_requests = list(final_state.get("evidence_requests") or pol.get("evidence_requests") or [])
    evidence_requests = []
    has_cust_confirmation_req = False

    for i, req in enumerate(raw_requests):
        if not isinstance(req, dict):
            continue
        req_id = req.get("request_id") or f"req_{i+1}_{case_id}"
        req_type = req.get("request_type", "customer_confirmation")
        if req_type == "customer_confirmation":
            has_cust_confirmation_req = True
        txn_id = str(req.get("transaction_id") or case_info.get("flagged_txn_id", ""))
        question = req.get("question") or f"Did you authorize transaction {txn_id}?"
        req_status = req.get("status", "pending")
        metadata = dict(req.get("metadata") or {})

        # Record customer communication assumption
        cust_status_for_req = req.get("customer_response_status") or customer_response_status
        metadata["customer_response_status"] = cust_status_for_req
        metadata["simulated_customer_response"] = (
            cust_status_for_req if cust_status_for_req in ("confirmed", "denied") else None
        )

        evidence_requests.append({
            "request_id": req_id,
            "request_type": req_type,
            "transaction_id": txn_id,
            "question": question,
            "status": req_status,
            "customer_response_status": cust_status_for_req,
            "metadata": metadata,
        })

    # If legitimate verdict without customer confirmation, ensure customer validation request is recorded
    if verdict == "legitimate" and customer_response_status != "confirmed" and not has_cust_confirmation_req:
        flagged_txn = str(case_info.get("flagged_txn_id") or final_state.get("flagged_txn_id", ""))
        evidence_requests.append({
            "request_id": f"req_cust_{flagged_txn}",
            "request_type": "customer_confirmation",
            "transaction_id": flagged_txn,
            "question": f"Did you authorize transaction {flagged_txn}?",
            "status": "pending",
            "customer_response_status": customer_response_status,
            "metadata": {
                "channel": "customer_outreach",
                "awaiting_response": True,
                "customer_response_status": customer_response_status,
                "simulated_customer_response": None,
                "reason": "Policy requires customer confirmation before closing legitimate case.",
            },
        })

    # 5. SAR (Suspicious Activity Report)
    is_file_report = "FILE_REPORT" in final_actions
    sar_file = False if verdict == "legitimate" else is_file_report

    sar_reasons = []
    if sar_file:
        if exposure_usd > 1000.0:
            sar_reasons.append(f"exposure (${exposure_usd:.2f} > $1,000)")
        if final_state.get("shared_device_fraud_cluster"):
            sar_reasons.append("shared device profile fraud cluster")
        if final_state.get("shared_region_fraud_cluster"):
            sar_reasons.append("shared billing region fraud cluster")
        if final_state.get("another_card_fraud_established"):
            sar_reasons.append("another card fraud established")
        if not sar_reasons:
            sar_reasons.append("Regulatory report required based on policy decision.")
    else:
        if verdict == "legitimate":
            sar_reasons.append("Transaction verified legitimate; no suspicious activity detected.")
        else:
            sar_reasons.append(f"SAR threshold not met (exposure ${exposure_usd:.2f} <= $1,000, no verified multi-card fraud cluster).")

    sar = {
        "file": sar_file,
        "reasons": sar_reasons,
    }

    # 6. Stop reason
    iteration_count = int(final_state.get("iteration_count", 0))
    tools_used = list(final_state.get("tools_used") or [])
    stop_reason = (
        final_state.get("stop_reason")
        or f"Investigation concluded: {len(tools_used)} tool call(s) over {iteration_count} iteration(s) evaluated across competing hypotheses."
    )

    # 7. Tool calls
    tool_calls = []
    for ev in final_state.get("evidence", []):
        if isinstance(ev, dict) and ev.get("source"):
            tool_calls.append({
                "tool": ev.get("source", ""),
                "args": ev.get("data", {}).get("arguments", {}),
            })
    if not tool_calls and tools_used:
        tool_calls = [{"tool": t, "args": {}} for t in tools_used]

    # 8. Tokens
    tokens = final_state.get("tokens") or {
        "prompt": int(final_state.get("prompt_tokens", 0)),
        "completion": int(final_state.get("completion_tokens", 0)),
        "total": int(final_state.get("total_tokens", 0)),
    }

    # 9. Latency
    latency = {
        "seconds": round(elapsed_seconds, 3),
        "ms": round(elapsed_seconds * 1000, 1),
    }

    # 10. Required Case Object
    case_obj = {
        "case_id": case_id,
        "customer_id": case_info.get("customer_id", final_state.get("customer_id")),
        "card_id": case_info.get("card_id", final_state.get("card_id")),
        "flagged_txn_id": str(case_info.get("flagged_txn_id", final_state.get("flagged_txn_id", ""))),
        "trigger_type": case_info.get("trigger_type"),
        "trigger_text": case_info.get("trigger_text"),
        "risk_score": case_info.get("risk_score"),
        "verdict": verdict,
        "fraud_probability": fraud_prob,
        "confidence": confidence,
        "exposure_usd": exposure_usd,
        "affected_txn_ids": affected_txn_ids,
        "fraud_type": fraud_type,
        "reasoning": ass.get("reasoning", ""),
        "customer_response_status": customer_response_status,
        "status": final_state.get("status", "completed"),
    }

    evidence_items = list(final_state.get("evidence") or [])
    hypotheses = list(final_state.get("hypotheses") or [])

    # Assemble complete schema containing both README required fields and backward-compatible fields
    record = {
        # README Contract Fields
        "case": case_obj,
        "evidence_requests": evidence_requests,
        "next_best_actions": next_best_actions,
        "sar": sar,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls,
        "tokens": tokens,
        "latency": latency,

        # Preserved internal structures for backward compatibility
        "case_id": case_id,
        "provider": provider_name,
        "model": model_name,
        "status": case_obj["status"],
        "runtime_seconds": latency["seconds"],
        "latency_ms": latency["ms"],
        "input": {
            "customer_id": case_obj["customer_id"],
            "card_id": case_obj["card_id"],
            "flagged_txn_id": case_obj["flagged_txn_id"],
            "trigger_type": case_info.get("trigger_type"),
            "trigger_text": case_info.get("trigger_text"),
            "risk_score": case_info.get("risk_score"),
        },
        "investigation": {
            "tools_used": tools_used,
            "tool_call_sequence": tools_used,
            "tool_call_count": len(tools_used),
            "evidence_count": len(evidence_items),
            "hypotheses": hypotheses,
            "evidence_requests": evidence_requests,
            "iteration_count": iteration_count,
        },
        "assessment": {
            "verdict": verdict,
            "fraud_probability": fraud_prob,
            "fraud_type": fraud_type,
            "exposure": exposure_usd,
            "affected_txn_ids": affected_txn_ids,
            "supporting_evidence": ass.get("supporting_evidence", []),
            "contradicting_evidence": ass.get("contradicting_evidence", []),
            "reasoning": ass.get("reasoning", ""),
            "confidence": confidence,
        },
        "policy": {
            "actions": final_actions,
            "primary_action": pol.get("primary_action"),
            "matched_rules": pol.get("matched_rules", []),
            "rationale": pol.get("rationale", ""),
            "requires_customer_response": pol.get("requires_customer_response", False) or (customer_response_status == "unknown" and len(evidence_requests) > 0),
            "evidence_requests": evidence_requests,
            "exposure": exposure_usd,
            "affected_txn_ids": affected_txn_ids,
            "customer_response_status": customer_response_status,
            "policy_conflicts": pol.get("policy_conflicts", []),
        },
        "errors": list(final_state.get("errors") or []),
    }

    return record


# Alias for serializer
serialize_case_output = adapt_to_output_contract
