"""
Output adapter for fraud investigation cases.
Serializes final case results to conform strictly to the authoritative README output contract:
Required top-level fields:
- case_id (str)
- case (dict with 15 required fields)
- evidence_requests (list)
- next_best_actions (dict with .initial and .final containing action objects)
- sar (dict with file, reason, narrative, subjects, total_amount_usd, activity_dates)
- stop_reason (str)
- tool_calls (int total count)
- tokens (int total count)
- latency_s (float elapsed wall-clock seconds)

Required case fields:
- status (str)
- verdict (str enum: confirmed_fraud | suspected_fraud | uncertain | legitimate)
- fraud_probability (float)
- pattern (str enum: card_testing | card_not_present_fraud | card_not_present_new_device |
                     out_of_region_use | account_takeover | undocumented | none)
- pattern_description (str)
- affected_txn_ids (list[str], [] for legitimate)
- first_suspicious_txn_id (str, "" for legitimate)
- connected_card_ids (list[str])
- connected_device_profiles (list[str])
- exposure_usd (float, 0.0 for legitimate)
- evidence (list[str])
- similar_prior_cases (list[str])
- summary (str)
- written_to_graph (bool, false when no evidence it was written)
- graph_case_id (str, "" when no graph case ID)

Preserves existing detailed internal structures (provider, model, input, investigation,
assessment, policy, errors, latency) for backward compatibility.
"""

import re
from typing import Any, Optional
from datetime import datetime, timezone

VALID_PATTERNS = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none",
}

VALID_ROUTES = {"auto", "L1", "L2"}

ACTION_ROUTE_MAP = {
    "BLOCK_CARD": "auto",
    "DECLINE_TRANSACTION": "auto",
    "STEP_UP_AUTH": "auto",
    "CREATE_CASE": "auto",
    "CLOSE_NO_FRAUD": "auto",
    "MONITOR_CARD": "auto",
    "MONITOR_CONNECTED_CARDS": "auto",
    "WARN_CUSTOMER": "auto",
    "VERIFY_WITH_CUSTOMER": "L1",
    "ESCALATE_TO_ANALYST": "L2",
    "FILE_REPORT": "L2",
}

ACTION_DEFAULT_REASONS = {
    "BLOCK_CARD": "Block card to prevent unauthorized charges on compromised payment instrument.",
    "DECLINE_TRANSACTION": "Decline transaction authorization due to high fraud risk.",
    "STEP_UP_AUTH": "Require step-up multi-factor authentication for high-risk or unconfirmed transaction.",
    "CREATE_CASE": "Mandatory case creation for fraud investigation.",
    "CLOSE_NO_FRAUD": "Close case with no fraud detected following customer authorization confirmation.",
    "MONITOR_CARD": "Place card on automated enhanced monitoring for suspicious activity.",
    "MONITOR_CONNECTED_CARDS": "Place connected cards sharing origin on enhanced monitoring.",
    "WARN_CUSTOMER": "Send security advisory notification to cardholder.",
    "VERIFY_WITH_CUSTOMER": "Route to L1 operations for cardholder transaction confirmation.",
    "ESCALATE_TO_ANALYST": "Escalate to L2 fraud analyst for manual investigation.",
    "FILE_REPORT": "Prepare and file Suspicious Activity Report (SAR) with regulatory authorities.",
}

PATTERN_DESCRIPTIONS = {
    "card_testing": "Rapid low-value authorizations followed by larger purchase attempt.",
    "card_not_present_fraud": "Unauthorized card-not-present online transaction.",
    "card_not_present_new_device": "Card-not-present online transaction executed from an unrecognized or shared device profile.",
    "out_of_region_use": "Transaction occurred in a new or anomalous billing region without prior cardholder history.",
    "account_takeover": "Account compromise involving unfamiliar device and anomalous access patterns.",
    "undocumented": "Identifiable undocumented fraud pattern across coordinated entities.",
    "none": "",
}


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


def format_action_object(
    item: Any,
    is_initial: bool = False,
    policy_rationale: str = "",
    fraud_prob: Optional[float] = None,
) -> dict[str, str]:
    """Formats an action string or dict into a standard {action, route, reason} object."""
    if isinstance(item, dict):
        action = str(item.get("action", "")).strip()
        route = item.get("route") or ACTION_ROUTE_MAP.get(action, "auto")
        reason = item.get("reason", "")
        if not reason:
            reason = ACTION_DEFAULT_REASONS.get(action, "")
        return {"action": action, "route": route, "reason": reason}

    action = str(item).strip()
    route = ACTION_ROUTE_MAP.get(action, "auto")
    reason = ACTION_DEFAULT_REASONS.get(action, "")

    if is_initial:
        if action == "VERIFY_WITH_CUSTOMER":
            reason = "Initial intake triage: route to L1 for cardholder verification."
        elif action == "CREATE_CASE":
            reason = "Initial intake triage: initialize case based on intake trigger."
        elif action == "STEP_UP_AUTH":
            reason = "Initial intake triage: require step-up authentication for online channel."
        elif action == "ESCALATE_TO_ANALYST":
            reason = "Initial intake triage: route analyst alert/request to L2 analyst."
    else:
        if action == "CREATE_CASE" and fraud_prob is not None and fraud_prob >= 0.30:
            reason = f"Mandatory case creation triggered: fraud probability ({fraud_prob:.2f} >= 0.30)."
        elif action == "CREATE_CASE" and policy_rationale and "GLOBAL_CREATE_CASE" in policy_rationale:
            reason = "Mandatory case creation triggered based on policy rules."
    return {"action": action, "route": route, "reason": reason}


def map_fraud_pattern(
    verdict: str,
    fraud_type: Optional[str],
    reasoning: str = "",
    is_undocumented: bool = False,
) -> tuple[str, str]:
    """
    Maps fraud_type to the authoritative README pattern enums:
    card_testing | card_not_present_fraud | card_not_present_new_device |
    out_of_region_use | account_takeover | undocumented | none.

    If fraud_type is not a recognized pattern (e.g. card_compromise),
    maps to 'none' unless evidence establishes an identifiable undocumented pattern.
    """
    if verdict == "legitimate":
        return "none", ""
    if is_undocumented:
        return "undocumented", PATTERN_DESCRIPTIONS["undocumented"]
    if not fraud_type:
        return "none", ""

    norm = str(fraud_type).strip().lower()
    if norm == "card_testing":
        return "card_testing", PATTERN_DESCRIPTIONS["card_testing"]
    elif norm in ("card_not_present_fraud", "card_not_present"):
        return "card_not_present_fraud", PATTERN_DESCRIPTIONS["card_not_present_fraud"]
    elif norm == "card_not_present_new_device":
        return "card_not_present_new_device", PATTERN_DESCRIPTIONS["card_not_present_new_device"]
    elif norm == "out_of_region_use":
        return "out_of_region_use", PATTERN_DESCRIPTIONS["out_of_region_use"]
    elif norm == "account_takeover":
        return "account_takeover", PATTERN_DESCRIPTIONS["account_takeover"]
    elif norm == "undocumented":
        return "undocumented", PATTERN_DESCRIPTIONS["undocumented"]
    else:
        return "none", ""


def extract_entities_from_state(
    state: dict[str, Any],
    case_info: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    """
    Extracts connected card IDs, device profiles, and similar prior cases
    from evidence and state without inventing new evidence.
    """
    ass = state.get("assessment") or {}
    inv = state.get("investigation") or {}
    supp = ass.get("supporting_evidence") or []
    contra = ass.get("contradicting_evidence") or []
    reasoning = ass.get("reasoning") or ""
    hypotheses = inv.get("hypotheses") or []

    hyp_texts: list[str] = []
    for h in hypotheses:
        if isinstance(h, dict):
            hyp_texts.append(h.get("description", ""))
            hyp_texts.extend(h.get("supporting_evidence", []))
            hyp_texts.extend(h.get("contradicting_evidence", []))

    corpus = " ".join(supp + contra + [reasoning] + hyp_texts)

    # Prior closed cases: CC-\d+
    prior_cases = sorted(set(re.findall(r"CC-\d+", corpus)))

    # Device profiles: SM-..., Trident/..., iPhone, iPad, etc.
    raw_devices = re.findall(r"(?:SM-[A-Za-z0-9]+(?:\s+Build/[A-Za-z0-9]+)?|Trident/[0-9.]+|iPhone|iPad)", corpus)
    devices: list[str] = []
    for dev in raw_devices:
        dev = dev.strip("'\"")
        if dev and dev not in devices:
            devices.append(dev)

    # Connected cards (cards other than the primary card)
    primary_card = (
        case_info.get("card_id")
        or state.get("card_id")
        or state.get("case", {}).get("card_id")
    )
    raw_cards = sorted(set(re.findall(r"C\d{4,6}-K\d", corpus)))
    connected_cards = [c for c in raw_cards if c != primary_card]

    if state.get("connected_card_ids"):
        connected_cards = list(state.get("connected_card_ids"))
    if state.get("connected_device_profiles"):
        devices = list(state.get("connected_device_profiles"))
    if state.get("similar_prior_cases"):
        prior_cases = list(state.get("similar_prior_cases"))

    return connected_cards, devices, prior_cases


def adapt_to_output_contract(
    case_info: dict[str, Any],
    final_state: dict[str, Any],
    elapsed_seconds: float = 0.0,
    provider_name: str = "mock",
    model_name: str = "unknown",
    initial_actions: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """
    Adapts an investigation final state into the authoritative README-compliant output contract.

    Guarantees:
    - Required top-level fields: case_id, case, evidence_requests, next_best_actions, sar,
      stop_reason, tool_calls, tokens, latency_s.
    - Required case fields: status, verdict, fraud_probability, pattern, pattern_description,
      affected_txn_ids, first_suspicious_txn_id, connected_card_ids, connected_device_profiles,
      exposure_usd, evidence, similar_prior_cases, summary, written_to_graph, graph_case_id.
    - next_best_actions.initial and .final contain {action, route, reason}.
    - sar contains {file, reason, narrative, subjects, total_amount_usd, activity_dates}.
    - legitimate cases have affected_txn_ids = [] and exposure_usd = 0.0.
    - When FILE_REPORT is not in final actions, SAR has empty narrative, subjects, amount 0.0, dates [].
    - tool_calls is an integer count.
    - tokens is an integer total.
    - latency_s is the elapsed wall-clock seconds (float).
    - Preserves internal structures for backward compatibility.
    """
    case_id = str(case_info.get("case_id") or final_state.get("case_id") or final_state.get("case", {}).get("case_id", ""))
    ass = final_state.get("assessment") or {}
    pol = final_state.get("policy_decision") or final_state.get("policy") or {}
    inv = final_state.get("investigation") or {}

    verdict = ass.get("verdict", "uncertain")
    fraud_prob = ass.get("fraud_probability")
    if fraud_prob is None:
        fraud_prob = 0.5
    fraud_prob = float(fraud_prob)
    confidence = float(ass.get("confidence", 0.5))

    # 1. Exposure and Affected Transactions
    if verdict == "legitimate":
        exposure_usd = 0.0
        affected_txn_ids: list[str] = []
        first_suspicious_txn_id = ""
        fraud_type = None
    else:
        exposure_usd = round(float(ass.get("exposure", pol.get("exposure", 0.0))), 2)
        affected_txn_ids = list(ass.get("affected_txn_ids", pol.get("affected_txn_ids", [])))
        flagged_txn = str(case_info.get("flagged_txn_id") or final_state.get("flagged_txn_id", ""))
        first_suspicious_txn_id = str(affected_txn_ids[0]) if affected_txn_ids else flagged_txn
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

    final_actions_raw = list(pol.get("actions") or [])
    pol_rationale = str(pol.get("rationale", ""))

    initial_formatted = [
        format_action_object(a, is_initial=True)
        for a in initial_actions
    ]
    final_formatted = [
        format_action_object(
            a,
            is_initial=False,
            policy_rationale=pol_rationale,
            fraud_prob=fraud_prob,
        )
        for a in final_actions_raw
    ]

    next_best_actions = {
        "initial": initial_formatted,
        "final": final_formatted,
    }

    final_action_names = [a["action"] for a in final_formatted]
    is_file_report = "FILE_REPORT" in final_action_names

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
    sar_file = False if verdict == "legitimate" else is_file_report
    sar_reasons: list[str] = []
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
        sar_reason_str = "; ".join(sar_reasons)
    else:
        if verdict == "legitimate":
            sar_reason_str = "Transaction verified legitimate; no suspicious activity detected."
        else:
            sar_reason_str = f"SAR threshold not met (exposure ${exposure_usd:.2f} <= $1,000, no verified multi-card fraud cluster)."

    if not sar_file or not is_file_report:
        sar = {
            "file": False,
            "reason": sar_reason_str,
            "narrative": "",
            "subjects": [],
            "total_amount_usd": 0.0,
            "activity_dates": [],
            "reasons": [sar_reason_str],  # Preserved for backward compatibility
        }
    else:
        cust_id = case_info.get("customer_id") or final_state.get("customer_id")
        card_id = case_info.get("card_id") or final_state.get("card_id")
        subjects = [s for s in [cust_id, card_id] if s]
        sar = {
            "file": True,
            "reason": sar_reason_str,
            "narrative": ass.get("reasoning", ""),
            "subjects": subjects,
            "total_amount_usd": round(exposure_usd, 2),
            "activity_dates": [case_info.get("opened_at")] if case_info.get("opened_at") else [],
            "reasons": sar_reasons,
        }

    # 6. Stop reason & Tool calls count
    iteration_count = int(final_state.get("iteration_count", 0))
    tools_used = list(final_state.get("tools_used") or inv.get("tools_used") or [])

    raw_tools = final_state.get("tool_calls")
    if isinstance(raw_tools, list):
        tool_calls_count = len(raw_tools)
        detailed_tool_calls = raw_tools
    elif isinstance(raw_tools, int):
        tool_calls_count = raw_tools
        detailed_tool_calls = []
    else:
        tool_calls_count = len(tools_used)
        detailed_tool_calls = []

    stop_reason = (
        final_state.get("stop_reason")
        or f"Investigation concluded: {tool_calls_count} tool call(s) over {iteration_count} iteration(s) evaluated across competing hypotheses."
    )

    # 7. Tokens (integer total)
    tokens_raw = final_state.get("tokens")
    if isinstance(tokens_raw, dict):
        tokens_total = int(tokens_raw.get("total", 0))
        tokens_dict = tokens_raw
    elif isinstance(tokens_raw, (int, float)):
        tokens_total = int(tokens_raw)
        tokens_dict = {"prompt": 0, "completion": 0, "total": tokens_total}
    else:
        tokens_total = int(final_state.get("total_tokens", 0))
        tokens_dict = {"prompt": 0, "completion": 0, "total": tokens_total}

    # 8. Latency (latency_s as float elapsed wall-clock seconds)
    lat_val = elapsed_seconds
    if not lat_val:
        lat_raw = final_state.get("latency_s")
        if lat_raw is None:
            lat_dict = final_state.get("latency")
            if isinstance(lat_dict, dict):
                lat_val = float(lat_dict.get("seconds", 0.0))
            elif isinstance(lat_dict, (int, float)):
                lat_val = float(lat_dict)
        else:
            lat_val = float(lat_raw)
    if not lat_val:
        lat_val = float(final_state.get("runtime_seconds", 0.0))
    latency_s = round(float(lat_val), 3)

    latency_dict = {
        "seconds": latency_s,
        "ms": round(latency_s * 1000, 1),
    }

    # 9. Pattern mapping & Entity extraction
    reasoning = str(ass.get("reasoning", ""))
    is_undoc = bool(final_state.get("undocumented_coordinated_abuse", False))
    pattern, pattern_desc = map_fraud_pattern(verdict, fraud_type, reasoning=reasoning, is_undocumented=is_undoc)
    connected_cards, connected_devices, prior_cases = extract_entities_from_state(final_state, case_info)

    evidence_items = list(ass.get("supporting_evidence") or [])
    summary = reasoning
    status = str(final_state.get("status") or "completed")

    # 10. Required Case Object
    case_obj = {
        # Authoritative README Required Fields
        "status": status,
        "verdict": verdict,
        "fraud_probability": fraud_prob,
        "pattern": pattern,
        "pattern_description": pattern_desc,
        "affected_txn_ids": affected_txn_ids,
        "first_suspicious_txn_id": first_suspicious_txn_id,
        "connected_card_ids": connected_cards,
        "connected_device_profiles": connected_devices,
        "exposure_usd": exposure_usd,
        "evidence": evidence_items,
        "similar_prior_cases": prior_cases,
        "summary": summary,
        "written_to_graph": False,
        "graph_case_id": "",

        # Preserved internal fields
        "case_id": case_id,
        "customer_id": case_info.get("customer_id", final_state.get("customer_id")),
        "card_id": case_info.get("card_id", final_state.get("card_id")),
        "flagged_txn_id": str(case_info.get("flagged_txn_id", final_state.get("flagged_txn_id", ""))),
        "trigger_type": case_info.get("trigger_type"),
        "trigger_text": case_info.get("trigger_text"),
        "risk_score": case_info.get("risk_score"),
        "confidence": confidence,
        "fraud_type": fraud_type,
        "reasoning": reasoning,
        "customer_response_status": customer_response_status,
    }

    hypotheses = list(final_state.get("hypotheses") or [])

    # Assemble complete schema containing both README required fields and backward-compatible fields
    record = {
        # Authoritative README Contract Fields
        "case_id": case_id,
        "case": case_obj,
        "evidence_requests": evidence_requests,
        "next_best_actions": next_best_actions,
        "sar": sar,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls_count,
        "tokens": tokens_total,
        "latency_s": latency_s,

        # Preserved internal structures for backward compatibility
        "provider": provider_name or final_state.get("provider", "mock"),
        "model": model_name or final_state.get("model", "unknown"),
        "status": status,
        "runtime_seconds": latency_s,
        "latency_ms": latency_dict["ms"],
        "latency": latency_dict,
        "input": final_state.get("input") or {
            "customer_id": case_obj["customer_id"],
            "card_id": case_obj["card_id"],
            "flagged_txn_id": case_obj["flagged_txn_id"],
            "trigger_type": case_info.get("trigger_type"),
            "trigger_text": case_info.get("trigger_text"),
            "risk_score": case_info.get("risk_score"),
        },
        "investigation": final_state.get("investigation") or {
            "tools_used": tools_used,
            "tool_call_sequence": tools_used,
            "tool_call_count": tool_calls_count,
            "evidence_count": len(evidence_items),
            "hypotheses": hypotheses,
            "evidence_requests": evidence_requests,
            "iteration_count": iteration_count,
            "tool_calls_detail": detailed_tool_calls,
        },
        "assessment": final_state.get("assessment") or {
            "verdict": verdict,
            "fraud_probability": fraud_prob,
            "fraud_type": fraud_type,
            "exposure": exposure_usd,
            "affected_txn_ids": affected_txn_ids,
            "supporting_evidence": evidence_items,
            "contradicting_evidence": ass.get("contradicting_evidence", []),
            "reasoning": reasoning,
            "confidence": confidence,
        },
        "policy": final_state.get("policy") or pol,
        "errors": list(final_state.get("errors") or []),
    }

    return record


def adapt_existing_result_to_case_contract(d: dict[str, Any]) -> dict[str, Any]:
    """
    Transforms an existing completed case result file (from results/HHG-xxx.json)
    into the strict authoritative README-compliant submission format.
    Does NOT call any LLM or re-run any investigation.
    """
    case_in = d.get("case", {})
    case_id = str(d.get("case_id") or case_in.get("case_id", ""))
    ass = d.get("assessment", {})
    pol = d.get("policy", {})
    inv = d.get("investigation", {})
    inp = d.get("input", {})

    status = str(case_in.get("status") or d.get("status") or "completed")
    verdict = str(case_in.get("verdict") or ass.get("verdict") or "uncertain")
    fraud_prob = case_in.get("fraud_probability")
    if fraud_prob is None:
        fraud_prob = ass.get("fraud_probability", 0.5)
    fraud_prob = float(fraud_prob)
    confidence = float(case_in.get("confidence", ass.get("confidence", 0.5)))

    if verdict == "legitimate":
        exposure_usd = 0.0
        affected_txn_ids = []
        first_suspicious_txn_id = ""
        fraud_type = None
    else:
        exposure_usd = round(float(case_in.get("exposure_usd") if case_in.get("exposure_usd") is not None else ass.get("exposure", pol.get("exposure", 0.0))), 2)
        affected_txn_ids = list(case_in.get("affected_txn_ids") or ass.get("affected_txn_ids") or pol.get("affected_txn_ids") or [])
        flagged_txn = str(case_in.get("flagged_txn_id") or inp.get("flagged_txn_id") or "")
        first_suspicious_txn_id = str(affected_txn_ids[0]) if affected_txn_ids else flagged_txn
        fraud_type = case_in.get("fraud_type") or ass.get("fraud_type")

    reasoning = str(case_in.get("reasoning") or ass.get("reasoning") or "")
    is_undoc = bool(d.get("undocumented_coordinated_abuse", False))
    pattern, pattern_desc = map_fraud_pattern(verdict, fraud_type, reasoning=reasoning, is_undocumented=is_undoc)

    connected_cards, connected_devices, prior_cases = extract_entities_from_state(d, case_in)
    evidence = list(ass.get("supporting_evidence") or [])
    summary = reasoning

    case_obj = {
        # Authoritative README Required Fields
        "status": status,
        "verdict": verdict,
        "fraud_probability": fraud_prob,
        "pattern": pattern,
        "pattern_description": pattern_desc,
        "affected_txn_ids": affected_txn_ids,
        "first_suspicious_txn_id": first_suspicious_txn_id,
        "connected_card_ids": connected_cards,
        "connected_device_profiles": connected_devices,
        "exposure_usd": exposure_usd,
        "evidence": evidence,
        "similar_prior_cases": prior_cases,
        "summary": summary,
        "written_to_graph": False,
        "graph_case_id": "",

        # Preserved internal fields
        "case_id": case_id,
        "customer_id": case_in.get("customer_id") or inp.get("customer_id"),
        "card_id": case_in.get("card_id") or inp.get("card_id"),
        "flagged_txn_id": str(case_in.get("flagged_txn_id") or inp.get("flagged_txn_id", "")),
        "trigger_type": case_in.get("trigger_type") or inp.get("trigger_type"),
        "trigger_text": case_in.get("trigger_text") or inp.get("trigger_text"),
        "risk_score": case_in.get("risk_score") if case_in.get("risk_score") is not None else inp.get("risk_score"),
        "confidence": confidence,
        "fraud_type": fraud_type,
        "reasoning": reasoning,
        "customer_response_status": case_in.get("customer_response_status") or pol.get("customer_response_status", "unknown"),
    }

    raw_nba = d.get("next_best_actions", {})
    initial_raw = raw_nba.get("initial", [])
    final_raw = raw_nba.get("final", [])
    pol_rationale = str(pol.get("rationale", ""))

    initial_formatted = [format_action_object(a, is_initial=True) for a in initial_raw]
    final_formatted = [format_action_object(a, is_initial=False, policy_rationale=pol_rationale, fraud_prob=fraud_prob) for a in final_raw]

    next_best_actions = {
        "initial": initial_formatted,
        "final": final_formatted,
    }

    final_action_names = [a["action"] for a in final_formatted]
    is_file_report = "FILE_REPORT" in final_action_names

    sar_in = d.get("sar", {})
    raw_reasons = sar_in.get("reasons") or sar_in.get("reason") or []
    if isinstance(raw_reasons, list):
        sar_reason_str = "; ".join(raw_reasons) if raw_reasons else ""
    else:
        sar_reason_str = str(raw_reasons)

    if not is_file_report or verdict == "legitimate":
        if not sar_reason_str:
            if verdict == "legitimate":
                sar_reason_str = "Transaction verified legitimate; no suspicious activity detected."
            else:
                sar_reason_str = f"SAR threshold not met (exposure ${exposure_usd:.2f} <= $1,000, no verified multi-card fraud cluster)."
        sar = {
            "file": False,
            "reason": sar_reason_str,
            "narrative": "",
            "subjects": [],
            "total_amount_usd": 0.0,
            "activity_dates": [],
            "reasons": [sar_reason_str],
        }
    else:
        cust_id = case_obj["customer_id"]
        card_id = case_obj["card_id"]
        subjects = [s for s in [cust_id, card_id] if s]
        sar = {
            "file": True,
            "reason": sar_reason_str or "Regulatory report required based on policy decision.",
            "narrative": summary,
            "subjects": subjects,
            "total_amount_usd": exposure_usd,
            "activity_dates": [inp.get("opened_at")] if inp.get("opened_at") else [],
            "reasons": [sar_reason_str],
        }

    raw_tool_calls = d.get("tool_calls")
    if isinstance(raw_tool_calls, list):
        tool_calls_count = len(raw_tool_calls)
        detailed_tool_calls = raw_tool_calls
    elif isinstance(raw_tool_calls, int):
        tool_calls_count = raw_tool_calls
        detailed_tool_calls = []
    else:
        tool_calls_count = len(inv.get("tools_used", []))
        detailed_tool_calls = []

    raw_tokens = d.get("tokens")
    if isinstance(raw_tokens, dict):
        tokens_total = int(raw_tokens.get("total", 0))
    elif isinstance(raw_tokens, (int, float)):
        tokens_total = int(raw_tokens)
    else:
        tokens_total = 0

    lat_val = d.get("latency_s")
    if lat_val is None:
        lat_dict = d.get("latency")
        if isinstance(lat_dict, dict):
            lat_val = lat_dict.get("seconds")
        elif isinstance(lat_dict, (int, float)):
            lat_val = lat_dict
    if lat_val is None:
        lat_val = d.get("runtime_seconds", 0.0)
    latency_s = round(float(lat_val), 3)

    stop_reason = str(d.get("stop_reason") or f"Investigation concluded: {tool_calls_count} tool call(s) evaluated across competing hypotheses.")
    evidence_requests = list(d.get("evidence_requests") or [])

    record = {
        # Authoritative README Top-Level Fields
        "case_id": case_id,
        "case": case_obj,
        "evidence_requests": evidence_requests,
        "next_best_actions": next_best_actions,
        "sar": sar,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls_count,
        "tokens": tokens_total,
        "latency_s": latency_s,

        # Preserved internal fields
        "provider": d.get("provider", "mock"),
        "model": d.get("model", "unknown"),
        "status": status,
        "runtime_seconds": latency_s,
        "latency_ms": round(latency_s * 1000, 1),
        "latency": {"seconds": latency_s, "ms": round(latency_s * 1000, 1)},
        "input": inp,
        "investigation": inv,
        "assessment": ass,
        "policy": pol,
        "errors": list(d.get("errors") or []),
    }
    return record


# Alias for serializer
serialize_case_output = adapt_to_output_contract
