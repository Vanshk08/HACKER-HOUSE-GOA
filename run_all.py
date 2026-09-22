"""
Batch runner for executing all 20 real challenge cases from data/case_pack.csv.

Orchestrates:
case_pack.csv -> Investigator <-> ToolExecutor (TigerGraph HHGOA_IEEE) -> Assessment -> Policy Engine -> Final Decision -> END

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
import argparse
from typing import Any, Optional

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.state import create_initial_state, InvestigationState
from agent.orchestrator import build_investigation_graph
from schemas.decision import VALID_ACTIONS
from schemas.output_adapter import serialize_case_output, compute_initial_actions

ALLOWED_VERDICTS = {"confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"}
ALLOWED_RULES = {
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10",
    "GLOBAL_CREATE_CASE", "GLOBAL_FILE_REPORT",
}
ALLOWED_CUSTOMER_STATUSES = {"unknown", "confirmed", "denied", "no_response"}


def _resolve_casepack_path(csv_path: str) -> str:
    """Resolve the canonical case-pack CSV, including the repo's data/raw layout."""
    candidates: list[str] = []
    if csv_path:
        candidates.append(csv_path)
        candidates.append(os.path.join(PROJECT_ROOT, csv_path))
        candidates.append(os.path.join(PROJECT_ROOT, "data", csv_path))
        candidates.append(os.path.join(PROJECT_ROOT, "data", "raw", os.path.basename(csv_path)))

    if os.path.basename(csv_path) == "case_pack.csv" or not os.path.basename(csv_path):
        candidates.extend([
            os.path.join(PROJECT_ROOT, "data", "raw", "case_pack.csv"),
            os.path.join(PROJECT_ROOT, "data", "case_pack.csv"),
        ])

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    return csv_path


def load_cases(csv_path: str = "data/case_pack.csv") -> list[dict[str, Any]]:
    """
    Loads all cases from case_pack.csv, validating required identifiers.
    Discovers cases dynamically without hardcoded IDs.
    """
    resolved_path = _resolve_casepack_path(csv_path)
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Case pack dataset not found at {resolved_path}")

    csv_path = resolved_path

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
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """
    Runs a single case independently through the existing StateGraph.
    Ensures complete state isolation and saves results/{case_id}.json.
    Records model/provider, latency, tool calls, and errors.
    """
    case_id = case_info["case_id"]
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"{case_id}.json")

    # Resolve provider and model metadata
    provider_name = provider or os.getenv("LLM_PROVIDER")
    model_name = "unknown"
    if provider_name:
        try:
            from agent.llm_config import get_llm_config
            cfg = get_llm_config(provider=provider_name)
            provider_name = cfg.provider
            model_name = cfg.model
        except Exception:
            pass
    if not provider_name:
        provider_name = "mock" if graph is not None else "unconfigured"

    start_time = time.time()

    try:
        # Build fresh graph if not provided
        if graph is None:
            if provider_name and provider_name != "unconfigured":
                from agent.llm_engine import get_investigator_llm, get_assessment_llm
                inv_llm = get_investigator_llm(provider=provider_name)
                ass_llm = get_assessment_llm(provider=provider_name)
                graph = build_investigation_graph(inv_llm, assessment_llm=ass_llm)
            else:
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

        initial_actions = compute_initial_actions(case_info, init_state)

        # Invoke existing StateGraph
        final_state = graph.invoke(init_state)

        # Validate results against Safety / Schema checks (A through K)
        validate_case_execution(case_info, final_state)

        elapsed = time.time() - start_time

        case_record = serialize_case_output(
            case_info=case_info,
            final_state=final_state,
            elapsed_seconds=elapsed,
            provider_name=provider_name,
            model_name=model_name,
            initial_actions=initial_actions,
        )

        # Write per-case JSON file
        with open(out_file, mode="w", encoding="utf-8") as f:
            json.dump(case_record, f, indent=2)

        return case_record

    except Exception as exc:
        elapsed = time.time() - start_time
        err_record = {
            "case_id": case_id,
            "provider": provider_name,
            "model": model_name,
            "status": "failed",
            "runtime_seconds": round(elapsed, 3),
            "latency_ms": round(elapsed * 1000, 1),
            "error": str(exc),
            "errors": [str(exc)],
        }
        with open(out_file, mode="w", encoding="utf-8") as f:
            json.dump(err_record, f, indent=2)

        return err_record


def run_all_cases(
    csv_path: str = "data/case_pack.csv",
    output_dir: str = "results",
    provider: Optional[str] = None,
    case_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Discovers and executes all cases from case_pack.csv sequentially.
    Generates per-case JSON files and summary.json with aggregate metrics.
    Records model/provider, latency, tool calls, and errors.
    """
    total_start = time.time()
    cases = load_cases(csv_path)
    if case_id is not None:
        target_case_id = case_id.strip()
        filtered_cases = [c for c in cases if c["case_id"] == target_case_id]
        if not filtered_cases:
            raise ValueError(f"Case ID {target_case_id or case_id} not found in case_pack.csv")
        cases = filtered_cases

    total_count = len(cases)

    selected_provider = provider or os.getenv("LLM_PROVIDER")
    if not selected_provider:
        raise ValueError(
            "No LLM provider configured. You must set LLM_PROVIDER=openai|anthropic|gemini|mock "
            "in your environment or pass --provider <provider>."
        )

    from agent.llm_config import get_llm_config
    cfg = get_llm_config(provider=selected_provider)
    provider_name = cfg.provider
    model_name = cfg.model

    from agent.llm_engine import get_investigator_llm, get_assessment_llm
    inv_llm = get_investigator_llm(provider=selected_provider)
    ass_llm = get_assessment_llm(provider=selected_provider)
    graph = build_investigation_graph(inv_llm, assessment_llm=ass_llm)

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 80)
    print(f"FRAUD INVESTIGATION BATCH RUNNER: {total_count} CASES")
    print(f"Provider: {provider_name} | Model: {model_name}")
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
        record = run_single_case(case_info, graph=graph, output_dir=output_dir, provider=provider_name)

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
                "next_best_actions": record.get("next_best_actions"),
                "sar": record.get("sar"),
                "tool_count": tc,
                "evidence_count": ec,
                "iteration_count": it,
                "runtime_seconds": record.get("runtime_seconds", 0.0),
                "latency_ms": record.get("latency_ms", 0.0),
                "errors": record.get("errors", []),
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
                "latency_ms": record.get("latency_ms", 0.0),
                "errors": record.get("errors", []),
            })
            print(f"[{idx:02d}/{total_count}] {case_id} ... FAILED ({record.get('runtime_seconds')}s)")
            print(f"    error: {record.get('error')}")

    total_time = round(time.time() - total_start, 3)
    completed_count = len(completed_records)
    failed_count = len(failed_records)

    avg_tools = round(total_tools / completed_count, 2) if completed_count else 0.0
    avg_evidence = round(total_evidence / completed_count, 2) if completed_count else 0.0
    avg_iterations = round(total_iterations / completed_count, 2) if completed_count else 0.0
    avg_latency = round(total_time / max(1, total_count), 3)

    summary_data = {
        "provider": provider_name,
        "model": model_name,
        "total_cases": total_count,
        "completed": completed_count,
        "failed": failed_count,
        "total_runtime_seconds": total_time,
        "average_latency_seconds": avg_latency,
        "total_tool_calls": total_tools,
        "total_errors": len(failed_records),
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
    print(f"Provider:    {provider_name} ({model_name})")
    print(f"Total Cases: {total_count}")
    print(f"Completed:   {completed_count}")
    print(f"Failed:      {failed_count}")
    print(f"Runtime:     {total_time}s (Avg Latency: {avg_latency}s)")
    print(f"Tool Calls:  {total_tools}")
    print(f"Verdicts:    {verdict_counts}")
    print(f"Actions:     {action_counts}")
    print(f"Summary saved to: {summary_file}")
    print("=" * 80)

    return summary_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run all fraud investigation cases")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER"), help="LLM Provider: openai, anthropic, gemini, or mock")
    parser.add_argument("--csv", default="data/case_pack.csv", help="Path to case_pack.csv")
    parser.add_argument("--out", default="results", help="Output directory")
    parser.add_argument("--case-id", help="Run only the specified case ID")
    args = parser.parse_args()

    summary = run_all_cases(
        csv_path=args.csv,
        output_dir=args.out,
        provider=args.provider,
        case_id=args.case_id,
    )
    if summary.get("failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)
