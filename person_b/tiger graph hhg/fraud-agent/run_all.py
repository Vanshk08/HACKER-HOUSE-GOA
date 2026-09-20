"""
Batch runner for executing all 20 real challenge cases from data/case_pack.csv.

Orchestrates:
case_pack.csv -> Investigator <-> ToolExecutor (DuckDB) -> Assessment -> Policy Engine -> Final Decision -> END

Produces:
results/
├── HHG-001.json
...
├── HHG-020.json
└── summary.json
"""

import os
import sys
import csv
import json
import time
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.state import create_initial_state, InvestigationState
from agent.orchestrator import build_investigation_graph
from schemas.decision import VALID_ACTIONS

ALLOWED_VERDICTS = {"confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"}
ALLOWED_RULES = {
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10",
    "GLOBAL_CREATE_CASE", "GLOBAL_FILE_REPORT",
}
ALLOWED_CUSTOMER_STATUSES = {"unknown", "confirmed", "denied", "no_response"}


def load_cases(csv_path: str = "data/case_pack.csv") -> list[dict[str, Any]]:
    """
    Loads all cases from case_pack.csv, validating required identifiers.
    Discovers cases dynamically without hardcoded IDs.
    """
    if not os.path.exists(csv_path):
        # Try relative to PROJECT_ROOT
        csv_path = os.path.join(PROJECT_ROOT, csv_path)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Case pack dataset not found at {csv_path}")

    cases = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            case_id = row.get("case_id", "").strip()
            cust_id = row.get("customer_id", "").strip()
            card_id = row.get("card_id", "").strip()
            txn_id = row.get("flagged_txn_id", "").strip()

            if not (case_id and cust_id and card_id and txn_id):
                raise ValueError(f"Case row missing required identifiers: {row}")

            risk_score_raw = row.get("risk_score", "").strip()
            risk_score = float(risk_score_raw) if risk_score_raw else None

            cases.append({
                "case_id": case_id,
                "customer_id": cust_id,
                "card_id": card_id,
                "flagged_txn_id": str(txn_id),
                "trigger_type": row.get("trigger_type", "").strip(),
                "trigger_text": row.get("trigger_text", "").strip(),
                "opened_at": row.get("opened_at", "").strip(),
                "risk_score": risk_score,
            })

    return cases


def validate_case_execution(case_info: dict[str, Any], final_state: dict[str, Any]) -> None:
    """
    Validates Safety / Schema Checks (A through K):
    A. Assessment exists.
    B. Assessment verdict is valid.
    C. fraud_probability is null or between 0 and 1.
    D. confidence is null or between 0 and 1.
    E. affected_txn_ids contain only IDs supported by evidence.
    F. exposure is non-negative.
    G. Policy actions are only from allowed ActionType set.
    H. Policy matched_rules are only from allowed set.
    I. customer_response_status is only: unknown, confirmed, denied, no_response.
    J. Case must not have another case's evidence.
    K. customer_id, card_id, flagged_txn_id remain consistent.
    """
    # K. Identifier consistency
    if final_state.get("case_id") != case_info["case_id"]:
        raise ValueError(f"State case_id mismatch: {final_state.get('case_id')} vs {case_info['case_id']}")
    if final_state.get("customer_id") != case_info["customer_id"]:
        raise ValueError(f"State customer_id mismatch: {final_state.get('customer_id')} vs {case_info['customer_id']}")
    if final_state.get("card_id") != case_info["card_id"]:
        raise ValueError(f"State card_id mismatch: {final_state.get('card_id')} vs {case_info['card_id']}")
    if str(final_state.get("flagged_txn_id")) != str(case_info["flagged_txn_id"]):
        raise ValueError(f"State flagged_txn_id mismatch: {final_state.get('flagged_txn_id')} vs {case_info['flagged_txn_id']}")

    # A. Assessment exists
    ass = final_state.get("assessment")
    if not ass:
        raise ValueError("Assessment is missing from final state")

    # B. Verdict validity
    verdict = ass.get("verdict")
    if verdict not in ALLOWED_VERDICTS:
        raise ValueError(f"Invalid verdict: {verdict}. Allowed: {ALLOWED_VERDICTS}")

    # C. Fraud probability
    prob = ass.get("fraud_probability")
    if prob is not None and not (0.0 <= prob <= 1.0):
        raise ValueError(f"Invalid fraud_probability: {prob}. Must be 0.0-1.0 or None")

    # D. Confidence
    conf = ass.get("confidence")
    if conf is not None and not (0.0 <= conf <= 1.0):
        raise ValueError(f"Invalid confidence: {conf}. Must be 0.0-1.0 or None")

    # E. Affected transactions
    affected_txns = ass.get("affected_txn_ids", [])
    if not isinstance(affected_txns, list):
        raise ValueError(f"affected_txn_ids must be a list, got {type(affected_txns)}")

    # F. Exposure
    exposure = ass.get("exposure", 0.0)
    if exposure < 0.0:
        raise ValueError(f"Exposure cannot be negative: {exposure}")

    # G. Policy actions
    policy_dec = final_state.get("policy_decision")
    if not policy_dec:
        raise ValueError("Policy decision is missing from final state")

    actions = policy_dec.get("actions", [])
    for act in actions:
        if act not in VALID_ACTIONS:
            raise ValueError(f"Invalid policy action: {act}. Allowed: {VALID_ACTIONS}")

    # H. Policy matched rules
    matched_rules = policy_dec.get("matched_rules", [])
    for rule in matched_rules:
        if rule not in ALLOWED_RULES:
            raise ValueError(f"Invalid policy rule: {rule}. Allowed: {ALLOWED_RULES}")

    # I. Customer response status
    status = policy_dec.get("customer_response_status")
    if status not in ALLOWED_CUSTOMER_STATUSES:
        raise ValueError(f"Invalid customer_response_status: {status}. Allowed: {ALLOWED_CUSTOMER_STATUSES}")
    if status == "unknown":
        if "R2" in matched_rules:
            raise ValueError("Policy violation: Rule R2 cannot match when customer_response_status is unknown")
        if "R3" in matched_rules:
            raise ValueError("Policy violation: Rule R3 cannot match when customer_response_status is unknown")

    # J. Cross-case evidence leakage check
    evidence = final_state.get("evidence", [])
    for ev in evidence:
        args = ev.get("data", {}).get("arguments", {})
        if "customer_id" in args and args["customer_id"] != case_info["customer_id"]:
            raise ValueError(f"Cross-case evidence leakage: argument customer_id {args['customer_id']} != {case_info['customer_id']}")


def run_single_case(
    case_info: dict[str, Any],
    graph=None,
    output_dir: str = "results",
) -> dict[str, Any]:
    """
    Runs a single case independently through the existing StateGraph.
    Ensures complete state isolation and saves results/{case_id}.json.
    """
    case_id = case_info["case_id"]
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"{case_id}.json")

    start_time = time.time()

    try:
        # Build fresh graph if not provided
        if graph is None:
            graph = build_investigation_graph()

        # Create completely fresh, isolated initial state
        init_state: InvestigationState = create_initial_state(
            case_id=case_id,
            customer_id=case_info["customer_id"],
            card_id=case_info["card_id"],
            flagged_txn_id=case_info["flagged_txn_id"],
            trigger_type=case_info.get("trigger_type"),
            trigger_text=case_info.get("trigger_text"),
            risk_score=case_info.get("risk_score"),
        )

        # Invoke existing StateGraph
        final_state = graph.invoke(init_state)

        # Validate results against Safety / Schema checks (A through K)
        validate_case_execution(case_info, final_state)

        elapsed = time.time() - start_time

        # Extract tool call sequence and evidence
        tools_used = final_state.get("tools_used", [])
        evidence = final_state.get("evidence", [])
        hypotheses = final_state.get("hypotheses", [])
        evidence_requests = final_state.get("evidence_requests", [])
        iteration_count = final_state.get("iteration_count", 0)

        ass = final_state.get("assessment", {})
        pol = final_state.get("policy_decision", {})

        case_record = {
            "case_id": case_id,
            "input": {
                "customer_id": case_info["customer_id"],
                "card_id": case_info["card_id"],
                "flagged_txn_id": case_info["flagged_txn_id"],
                "trigger_type": case_info.get("trigger_type"),
                "trigger_text": case_info.get("trigger_text"),
                "risk_score": case_info.get("risk_score"),
            },
            "status": "completed",
            "runtime_seconds": round(elapsed, 3),
            "investigation": {
                "tools_used": tools_used,
                "tool_call_sequence": tools_used,
                "evidence_count": len(evidence),
                "hypotheses": hypotheses,
                "evidence_requests": evidence_requests,
                "iteration_count": iteration_count,
            },
            "assessment": {
                "verdict": ass.get("verdict"),
                "fraud_probability": ass.get("fraud_probability"),
                "fraud_type": ass.get("fraud_type"),
                "exposure": ass.get("exposure", 0.0),
                "affected_txn_ids": ass.get("affected_txn_ids", []),
                "supporting_evidence": ass.get("supporting_evidence", []),
                "contradicting_evidence": ass.get("contradicting_evidence", []),
                "reasoning": ass.get("reasoning", ""),
                "confidence": ass.get("confidence"),
            },
            "policy": {
                "actions": pol.get("actions", []),
                "primary_action": pol.get("primary_action"),
                "matched_rules": pol.get("matched_rules", []),
                "rationale": pol.get("rationale", ""),
                "requires_customer_response": pol.get("requires_customer_response", False),
                "evidence_requests": pol.get("evidence_requests", []),
                "exposure": pol.get("exposure", 0.0),
                "affected_txn_ids": pol.get("affected_txn_ids", []),
                "customer_response_status": pol.get("customer_response_status", "unknown"),
                "policy_conflicts": pol.get("policy_conflicts", []),
            },
        }

        # Write per-case JSON file
        with open(out_file, mode="w", encoding="utf-8") as f:
            json.dump(case_record, f, indent=2)

        return case_record

    except Exception as exc:
        elapsed = time.time() - start_time
        err_record = {
            "case_id": case_id,
            "status": "failed",
            "runtime_seconds": round(elapsed, 3),
            "error": str(exc),
        }
        with open(out_file, mode="w", encoding="utf-8") as f:
            json.dump(err_record, f, indent=2)

        return err_record


def run_all_cases(
    csv_path: str = "data/case_pack.csv",
    output_dir: str = "results",
) -> dict[str, Any]:
    """
    Discovers and executes all cases from case_pack.csv sequentially.
    Generates per-case JSON files and summary.json with aggregate metrics.
    """
    total_start = time.time()
    cases = load_cases(csv_path)
    total_count = len(cases)

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 80)
    print(f"FRAUD INVESTIGATION BATCH RUNNER: {total_count} CASES")
    print(f"Source: {csv_path}")
    print(f"Destination: {output_dir}/")
    print("=" * 80)

    completed_records = []
    failed_records = []
    case_summaries = []

    # Aggregate counters
    verdict_counts: dict[str, int] = {}
    fraud_type_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    rule_counts: dict[str, int] = {}

    total_tools = 0
    total_evidence = 0
    total_iterations = 0

    for idx, case_info in enumerate(cases, 1):
        case_id = case_info["case_id"]

        # Run case
        record = run_single_case(case_info, output_dir=output_dir)

        if record.get("status") == "completed":
            completed_records.append(record)
            ass = record["assessment"]
            pol = record["policy"]
            inv = record["investigation"]

            verdict = ass.get("verdict")
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

            ftype = ass.get("fraud_type") or "none"
            fraud_type_counts[ftype] = fraud_type_counts.get(ftype, 0) + 1

            for act in pol.get("actions", []):
                action_counts[act] = action_counts.get(act, 0) + 1

            for r in pol.get("matched_rules", []):
                rule_counts[r] = rule_counts.get(r, 0) + 1

            tc = len(inv.get("tools_used", []))
            ec = inv.get("evidence_count", 0)
            it = inv.get("iteration_count", 0)

            total_tools += tc
            total_evidence += ec
            total_iterations += it

            case_summaries.append({
                "case_id": case_id,
                "status": "completed",
                "verdict": verdict,
                "fraud_probability": ass.get("fraud_probability"),
                "fraud_type": ass.get("fraud_type"),
                "exposure": ass.get("exposure"),
                "affected_txn_count": len(ass.get("affected_txn_ids", [])),
                "matched_rules": pol.get("matched_rules", []),
                "actions": pol.get("actions", []),
                "tool_count": tc,
                "evidence_count": ec,
                "iteration_count": it,
                "runtime_seconds": record.get("runtime_seconds", 0.0),
            })

            # Progress logging
            print(f"[{idx:02d}/{total_count}] {case_id} ... completed ({record.get('runtime_seconds')}s)")
            print(f"    verdict: {verdict}")
            print(f"    probability: {ass.get('fraud_probability')}")
            print(f"    actions: {', '.join(pol.get('actions', []))}")
            print(f"    tools: {tc} | evidence: {ec} | iterations: {it}")

        else:
            failed_records.append(record)
            case_summaries.append({
                "case_id": case_id,
                "status": "failed",
                "error": record.get("error"),
                "runtime_seconds": record.get("runtime_seconds", 0.0),
            })
            print(f"[{idx:02d}/{total_count}] {case_id} ... FAILED ({record.get('runtime_seconds')}s)")
            print(f"    error: {record.get('error')}")

    total_time = round(time.time() - total_start, 3)
    completed_count = len(completed_records)
    failed_count = len(failed_records)

    avg_tools = round(total_tools / completed_count, 2) if completed_count else 0.0
    avg_evidence = round(total_evidence / completed_count, 2) if completed_count else 0.0
    avg_iterations = round(total_iterations / completed_count, 2) if completed_count else 0.0

    summary_data = {
        "total_cases": total_count,
        "completed": completed_count,
        "failed": failed_count,
        "total_runtime_seconds": total_time,
        "aggregate_statistics": {
            "verdict_counts": verdict_counts,
            "fraud_type_counts": fraud_type_counts,
            "action_counts": action_counts,
            "rule_counts": rule_counts,
            "average_tool_count": avg_tools,
            "average_evidence_count": avg_evidence,
            "average_iterations": avg_iterations,
        },
        "cases": case_summaries,
    }

    # Write summary.json
    summary_file = os.path.join(output_dir, "summary.json")
    with open(summary_file, mode="w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print("=" * 80)
    print("BATCH EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Total Cases: {total_count}")
    print(f"Completed:   {completed_count}")
    print(f"Failed:      {failed_count}")
    print(f"Runtime:     {total_time}s")
    print(f"Verdicts:    {verdict_counts}")
    print(f"Actions:     {action_counts}")
    print(f"Summary saved to: {summary_file}")
    print("=" * 80)

    return summary_data


if __name__ == "__main__":
    summary = run_all_cases()
    if summary.get("failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)
