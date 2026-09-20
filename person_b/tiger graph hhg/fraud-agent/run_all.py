# run_all.py

import os
import sys
import csv
import json
import time
from typing import Any


"""
Batch runner for executing all real challenge cases from
the repository-level data/case_pack.csv.

Workflow:

case_pack.csv
    ↓
InvestigationAgent
    ↓
TigerGraph Investigation Tool
    ↓
Customer Validation
    ↓
Assessment
    ↓
Policy Engine
    ↓
Final Decision
    ↓
END

Produces:

results/
├── HHG-001.json
├── HHG-002.json
├── ...
├── HHG-020.json
└── summary.json
"""


# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# Repository root:
#
# HACKER-HOUSE-GOA/
# ├── data/
# └── person_b/
#     └── tiger graph hhg/
#         └── fraud-agent/   <-- PROJECT_ROOT
#
# Therefore:
#
# fraud-agent -> tiger graph hhg -> person_b -> HACKER-HOUSE-GOA
#
REPOSITORY_ROOT = os.path.abspath(
    os.path.join(
        PROJECT_ROOT,
        "..",
        "..",
        "..",
    )
)

DEFAULT_CASE_PACK = os.path.join(
    REPOSITORY_ROOT,
    "data",
    "raw",
    "case_pack.csv",
)

# ------------------------------------------------------------
# Project imports
# ------------------------------------------------------------

from agent.state import create_initial_state, InvestigationState
from agent.orchestrator import InvestigationOrchestrator
from agent.llm_engine import AutonomousInvestigatorLLM
from schemas.decision import VALID_ACTIONS


# ------------------------------------------------------------
# Validation constants
# ------------------------------------------------------------

ALLOWED_VERDICTS = {
    "confirmed_fraud",
    "suspected_fraud",
    "uncertain",
    "legitimate",
}

ALLOWED_RULES = {
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6",
    "R7",
    "R8",
    "R9",
    "R10",
    "GLOBAL_CREATE_CASE",
    "GLOBAL_FILE_REPORT",
}

ALLOWED_CUSTOMER_STATUSES = {
    "unknown",
    "confirmed",
    "denied",
    "no_response",
}


# ------------------------------------------------------------
# Case loading
# ------------------------------------------------------------

def load_cases(
    csv_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Load all cases from the repository-level case_pack.csv.

    Required identifiers:
        - case_id
        - customer_id
        - card_id
        - flagged_txn_id

    Cases are discovered dynamically from the CSV.
    """

    if csv_path is None:
        csv_path = DEFAULT_CASE_PACK
    else:
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(
                REPOSITORY_ROOT,
                csv_path,
            )

    csv_path = os.path.abspath(csv_path)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Case pack dataset not found at {csv_path}"
        )

    cases = []

    with open(
        csv_path,
        mode="r",
        encoding="utf-8",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            case_id = row.get(
                "case_id",
                "",
            ).strip()

            customer_id = row.get(
                "customer_id",
                "",
            ).strip()

            card_id = row.get(
                "card_id",
                "",
            ).strip()

            transaction_id = row.get(
                "flagged_txn_id",
                "",
            ).strip()

            if not (
                case_id
                and customer_id
                and card_id
                and transaction_id
            ):
                raise ValueError(
                    "Case row missing required identifiers: "
                    f"{row}"
                )

            risk_score_raw = row.get(
                "risk_score",
                "",
            ).strip()

            risk_score = (
                float(risk_score_raw)
                if risk_score_raw
                else None
            )

            cases.append(
                {
                    "case_id": case_id,
                    "customer_id": customer_id,
                    "card_id": card_id,
                    "flagged_txn_id": str(
                        transaction_id
                    ),
                    "trigger_type": row.get(
                        "trigger_type",
                        "",
                    ).strip(),
                    "trigger_text": row.get(
                        "trigger_text",
                        "",
                    ).strip(),
                    "opened_at": row.get(
                        "opened_at",
                        "",
                    ).strip(),
                    "risk_score": risk_score,
                }
            )

    return cases


# ------------------------------------------------------------
# Case validation
# ------------------------------------------------------------

def validate_case_execution(
    case_info: dict[str, Any],
    final_state: dict[str, Any],
) -> None:
    """
    Validate safety and schema checks.

    A. Assessment exists.
    B. Assessment verdict is valid.
    C. fraud_probability is null or between 0 and 1.
    D. confidence is null or between 0 and 1.
    E. affected_txn_ids is a list.
    F. exposure is non-negative.
    G. Policy actions are valid.
    H. Policy matched_rules are valid.
    I. Customer response status is valid.
    J. Cross-case evidence leakage is prevented.
    K. Case identifiers remain consistent.
    """

    # --------------------------------------------------------
    # K. Identifier consistency
    # --------------------------------------------------------

    if final_state.get("case_id") != case_info["case_id"]:
        raise ValueError(
            "State case_id mismatch: "
            f"{final_state.get('case_id')} "
            f"vs {case_info['case_id']}"
        )

    if final_state.get("customer_id") != case_info["customer_id"]:
        raise ValueError(
            "State customer_id mismatch: "
            f"{final_state.get('customer_id')} "
            f"vs {case_info['customer_id']}"
        )

    if final_state.get("card_id") != case_info["card_id"]:
        raise ValueError(
            "State card_id mismatch: "
            f"{final_state.get('card_id')} "
            f"vs {case_info['card_id']}"
        )

    if str(
        final_state.get("flagged_txn_id")
    ) != str(
        case_info["flagged_txn_id"]
    ):
        raise ValueError(
            "State flagged_txn_id mismatch: "
            f"{final_state.get('flagged_txn_id')} "
            f"vs {case_info['flagged_txn_id']}"
        )

    # --------------------------------------------------------
    # A. Assessment exists
    # --------------------------------------------------------

    assessment = final_state.get(
        "assessment"
    )

    if not assessment:
        raise ValueError(
            "Assessment is missing from final state"
        )

    # --------------------------------------------------------
    # B. Verdict validity
    # --------------------------------------------------------

    verdict = assessment.get(
        "verdict"
    )

    if verdict not in ALLOWED_VERDICTS:
        raise ValueError(
            f"Invalid verdict: {verdict}. "
            f"Allowed: {ALLOWED_VERDICTS}"
        )

    # --------------------------------------------------------
    # C. Fraud probability
    # --------------------------------------------------------

    fraud_probability = assessment.get(
        "fraud_probability"
    )

    if (
        fraud_probability is not None
        and not (
            0.0
            <= fraud_probability
            <= 1.0
        )
    ):
        raise ValueError(
            "Invalid fraud_probability: "
            f"{fraud_probability}. "
            "Must be 0.0-1.0 or None"
        )

    # --------------------------------------------------------
    # D. Confidence
    # --------------------------------------------------------

    confidence = assessment.get(
        "confidence"
    )

    if (
        confidence is not None
        and not (
            0.0
            <= confidence
            <= 1.0
        )
    ):
        raise ValueError(
            "Invalid confidence: "
            f"{confidence}. "
            "Must be 0.0-1.0 or None"
        )

    # --------------------------------------------------------
    # E. Affected transactions
    # --------------------------------------------------------

    affected_txns = assessment.get(
        "affected_txn_ids",
        [],
    )

    if not isinstance(
        affected_txns,
        list,
    ):
        raise ValueError(
            "affected_txn_ids must be a list"
        )

    # --------------------------------------------------------
    # F. Exposure
    # --------------------------------------------------------

    exposure = assessment.get(
        "exposure",
        0.0,
    )

    if exposure < 0.0:
        raise ValueError(
            f"Exposure cannot be negative: {exposure}"
        )

    # --------------------------------------------------------
    # G. Policy actions
    # --------------------------------------------------------

    policy_decision = final_state.get(
        "policy_decision"
    )

    if not policy_decision:
        raise ValueError(
            "Policy decision is missing from final state"
        )

    actions = policy_decision.get(
        "actions",
        [],
    )

    for action in actions:

        if action not in VALID_ACTIONS:
            raise ValueError(
                f"Invalid policy action: {action}. "
                f"Allowed: {VALID_ACTIONS}"
            )

    # --------------------------------------------------------
    # H. Policy matched rules
    # --------------------------------------------------------

    matched_rules = policy_decision.get(
        "matched_rules",
        [],
    )

    for rule in matched_rules:

        if rule not in ALLOWED_RULES:
            raise ValueError(
                f"Invalid policy rule: {rule}. "
                f"Allowed: {ALLOWED_RULES}"
            )

    # --------------------------------------------------------
    # I. Customer response status
    # --------------------------------------------------------

    customer_status = policy_decision.get(
        "customer_response_status"
    )

    if (
        customer_status
        not in ALLOWED_CUSTOMER_STATUSES
    ):
        raise ValueError(
            "Invalid customer_response_status: "
            f"{customer_status}. "
            f"Allowed: {ALLOWED_CUSTOMER_STATUSES}"
        )

    if customer_status == "unknown":

        if "R2" in matched_rules:
            raise ValueError(
                "Policy violation: "
                "Rule R2 cannot match when "
                "customer_response_status is unknown"
            )

        if "R3" in matched_rules:
            raise ValueError(
                "Policy violation: "
                "Rule R3 cannot match when "
                "customer_response_status is unknown"
            )

    # --------------------------------------------------------
    # J. Cross-case evidence leakage
    # --------------------------------------------------------

    evidence = final_state.get(
        "evidence",
        [],
    )

    for evidence_item in evidence:

        arguments = (
            evidence_item
            .get("data", {})
            .get("arguments", {})
        )

        if (
            "customer_id" in arguments
            and arguments["customer_id"]
            != case_info["customer_id"]
        ):
            raise ValueError(
                "Cross-case evidence leakage: "
                f"argument customer_id "
                f"{arguments['customer_id']} "
                f"!= "
                f"{case_info['customer_id']}"
            )


# ------------------------------------------------------------
# Single case execution
# ------------------------------------------------------------

def run_single_case(
    case_info: dict[str, Any],
    orchestrator: InvestigationOrchestrator,
    output_dir: str = "results",
) -> dict[str, Any]:
    """
    Run one case independently through the
    InvestigationOrchestrator.

    Each case receives a fresh state.

    Results are written to:

        results/{case_id}.json
    """

    case_id = case_info["case_id"]

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    output_file = os.path.join(
        output_dir,
        f"{case_id}.json",
    )

    start_time = time.time()

    try:

        # ----------------------------------------------------
        # Fresh isolated state
        # ----------------------------------------------------

        initial_state: InvestigationState = (
            create_initial_state(
                case_id=case_id,
                customer_id=case_info[
                    "customer_id"
                ],
                card_id=case_info[
                    "card_id"
                ],
                flagged_txn_id=case_info[
                    "flagged_txn_id"
                ],
                trigger_type=case_info.get(
                    "trigger_type"
                ),
                trigger_text=case_info.get(
                    "trigger_text"
                ),
                risk_score=case_info.get(
                    "risk_score"
                ),
            )
        )

        # ----------------------------------------------------
        # Run through the tested orchestrator.
        #
        # This uses:
        #
        # InvestigationAgent
        #       ↓
        # TigerGraph
        #       ↓
        # Customer validation
        #       ↓
        # Assessment
        #       ↓
        # Policy
        #       ↓
        # END
        # ----------------------------------------------------

        final_state = orchestrator.run(
            initial_state
        )

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        validate_case_execution(
            case_info,
            final_state,
        )

        elapsed = time.time() - start_time

        # ----------------------------------------------------
        # Extract results
        # ----------------------------------------------------

        tools_used = final_state.get(
            "tools_used",
            [],
        )

        evidence = final_state.get(
            "evidence",
            [],
        )

        hypotheses = final_state.get(
            "hypotheses",
            [],
        )

        evidence_requests = final_state.get(
            "evidence_requests",
            [],
        )

        iteration_count = final_state.get(
            "iteration_count",
            0,
        )

        assessment = final_state.get(
            "assessment",
            {},
        )

        policy = final_state.get(
            "policy_decision",
            {},
        )

        # ----------------------------------------------------
        # Build result record
        # ----------------------------------------------------

        case_record = {
            "case_id": case_id,

            "input": {
                "customer_id": case_info[
                    "customer_id"
                ],
                "card_id": case_info[
                    "card_id"
                ],
                "flagged_txn_id": case_info[
                    "flagged_txn_id"
                ],
                "trigger_type": case_info.get(
                    "trigger_type"
                ),
                "trigger_text": case_info.get(
                    "trigger_text"
                ),
                "risk_score": case_info.get(
                    "risk_score"
                ),
            },

            "status": "completed",

            "runtime_seconds": round(
                elapsed,
                3,
            ),

            "stop": final_state.get(
                "stop",
                False,
            ),

            "stop_reason": final_state.get(
                "stop_reason"
            ),

            "investigation": {
                "tools_used": tools_used,

                "tool_call_sequence": tools_used,

                "evidence_count": len(
                    evidence
                ),

                "hypotheses": hypotheses,

                "evidence_requests": (
                    evidence_requests
                ),

                "iteration_count": (
                    iteration_count
                ),
            },

            "assessment": {
                "verdict": assessment.get(
                    "verdict"
                ),

                "fraud_probability": (
                    assessment.get(
                        "fraud_probability"
                    )
                ),

                "fraud_type": assessment.get(
                    "fraud_type"
                ),

                "exposure": assessment.get(
                    "exposure",
                    0.0,
                ),

                "affected_txn_ids": (
                    assessment.get(
                        "affected_txn_ids",
                        [],
                    )
                ),

                "supporting_evidence": (
                    assessment.get(
                        "supporting_evidence",
                        [],
                    )
                ),

                "contradicting_evidence": (
                    assessment.get(
                        "contradicting_evidence",
                        [],
                    )
                ),

                "reasoning": assessment.get(
                    "reasoning",
                    "",
                ),

                "confidence": assessment.get(
                    "confidence"
                ),
            },

            "policy": {
                "actions": policy.get(
                    "actions",
                    [],
                ),

                "primary_action": policy.get(
                    "primary_action"
                ),

                "matched_rules": policy.get(
                    "matched_rules",
                    [],
                ),

                "rationale": policy.get(
                    "rationale",
                    "",
                ),

                "requires_customer_response": (
                    policy.get(
                        "requires_customer_response",
                        False,
                    )
                ),

                "evidence_requests": (
                    policy.get(
                        "evidence_requests",
                        [],
                    )
                ),

                "exposure": policy.get(
                    "exposure",
                    0.0,
                ),

                "affected_txn_ids": (
                    policy.get(
                        "affected_txn_ids",
                        [],
                    )
                ),

                "customer_response_status": (
                    policy.get(
                        "customer_response_status",
                        "unknown",
                    )
                ),

                "policy_conflicts": (
                    policy.get(
                        "policy_conflicts",
                        [],
                    )
                ),
            },
        }

        # ----------------------------------------------------
        # Write case result
        # ----------------------------------------------------

        with open(
            output_file,
            mode="w",
            encoding="utf-8",
        ) as f:

            json.dump(
                case_record,
                f,
                indent=2,
            )

        return case_record

    except Exception as exc:

        elapsed = time.time() - start_time

        error_record = {
            "case_id": case_id,
            "status": "failed",
            "runtime_seconds": round(
                elapsed,
                3,
            ),
            "error": str(exc),
        }

        with open(
            output_file,
            mode="w",
            encoding="utf-8",
        ) as f:

            json.dump(
                error_record,
                f,
                indent=2,
            )

        return error_record


# ------------------------------------------------------------
# Batch execution
# ------------------------------------------------------------

def run_all_cases(
    csv_path: str | None = None,
    output_dir: str = "results",
) -> dict[str, Any]:
    """
    Execute every case from case_pack.csv sequentially.

    Generates:

        results/{case_id}.json
        results/summary.json
    """

    total_start = time.time()

    cases = load_cases(
        csv_path
    )

    total_count = len(
        cases
    )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    print("=" * 80)
    print(
        "FRAUD INVESTIGATION BATCH RUNNER: "
        f"{total_count} CASES"
    )
    print(
        f"Source: {csv_path or DEFAULT_CASE_PACK}"
    )
    print(
        f"Destination: {output_dir}/"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # Build one tested orchestrator.
    # --------------------------------------------------------

    investigator_llm = (
        AutonomousInvestigatorLLM()
    )

    orchestrator = InvestigationOrchestrator(
        investigator_llm
    )

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

    # --------------------------------------------------------
    # Execute every case
    # --------------------------------------------------------

    for idx, case_info in enumerate(
        cases,
        1,
    ):

        case_id = case_info[
            "case_id"
        ]

        record = run_single_case(
            case_info,
            orchestrator,
            output_dir,
        )

        if record.get(
            "status"
        ) == "completed":

            completed_records.append(
                record
            )

            assessment = record[
                "assessment"
            ]

            policy = record[
                "policy"
            ]

            investigation = record[
                "investigation"
            ]

            verdict = assessment.get(
                "verdict"
            )

            verdict_counts[
                verdict
            ] = verdict_counts.get(
                verdict,
                0,
            ) + 1

            fraud_type = (
                assessment.get(
                    "fraud_type"
                )
                or "none"
            )

            fraud_type_counts[
                fraud_type
            ] = fraud_type_counts.get(
                fraud_type,
                0,
            ) + 1

            for action in policy.get(
                "actions",
                [],
            ):

                action_counts[
                    action
                ] = action_counts.get(
                    action,
                    0,
                ) + 1

            for rule in policy.get(
                "matched_rules",
                [],
            ):

                rule_counts[
                    rule
                ] = rule_counts.get(
                    rule,
                    0,
                ) + 1

            tool_count = len(
                investigation.get(
                    "tools_used",
                    [],
                )
            )

            evidence_count = investigation.get(
                "evidence_count",
                0,
            )

            iteration_count = investigation.get(
                "iteration_count",
                0,
            )

            total_tools += tool_count
            total_evidence += evidence_count
            total_iterations += iteration_count

            case_summaries.append(
                {
                    "case_id": case_id,
                    "status": "completed",
                    "verdict": verdict,
                    "fraud_probability": (
                        assessment.get(
                            "fraud_probability"
                        )
                    ),
                    "fraud_type": (
                        assessment.get(
                            "fraud_type"
                        )
                    ),
                    "exposure": (
                        assessment.get(
                            "exposure"
                        )
                    ),
                    "affected_txn_count": len(
                        assessment.get(
                            "affected_txn_ids",
                            [],
                        )
                    ),
                    "matched_rules": (
                        policy.get(
                            "matched_rules",
                            [],
                        )
                    ),
                    "actions": (
                        policy.get(
                            "actions",
                            [],
                        )
                    ),
                    "tool_count": tool_count,
                    "evidence_count": evidence_count,
                    "iteration_count": iteration_count,
                    "runtime_seconds": record.get(
                        "runtime_seconds",
                        0.0,
                    ),
                }
            )

            print(
                f"[{idx:02d}/{total_count}] "
                f"{case_id} ... completed "
                f"({record.get('runtime_seconds')}s)"
            )

            print(
                f"    verdict: {verdict}"
            )

            print(
                "    probability: "
                f"{assessment.get('fraud_probability')}"
            )

            print(
                "    actions: "
                f"{', '.join(policy.get('actions', []))}"
            )

            print(
                f"    tools: {tool_count} | "
                f"evidence: {evidence_count} | "
                f"iterations: {iteration_count}"
            )

        else:

            failed_records.append(
                record
            )

            case_summaries.append(
                {
                    "case_id": case_id,
                    "status": "failed",
                    "error": record.get(
                        "error"
                    ),
                    "runtime_seconds": record.get(
                        "runtime_seconds",
                        0.0,
                    ),
                }
            )

            print(
                f"[{idx:02d}/{total_count}] "
                f"{case_id} ... FAILED "
                f"({record.get('runtime_seconds')}s)"
            )

            print(
                f"    error: {record.get('error')}"
            )

    # --------------------------------------------------------
    # Aggregate statistics
    # --------------------------------------------------------

    total_time = round(
        time.time() - total_start,
        3,
    )

    completed_count = len(
        completed_records
    )

    failed_count = len(
        failed_records
    )

    average_tools = (
        round(
            total_tools
            / completed_count,
            2,
        )
        if completed_count
        else 0.0
    )

    average_evidence = (
        round(
            total_evidence
            / completed_count,
            2,
        )
        if completed_count
        else 0.0
    )

    average_iterations = (
        round(
            total_iterations
            / completed_count,
            2,
        )
        if completed_count
        else 0.0
    )

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
            "average_tool_count": average_tools,
            "average_evidence_count": average_evidence,
            "average_iterations": average_iterations,
        },

        "cases": case_summaries,
    }

    # --------------------------------------------------------
    # Write summary.json
    # --------------------------------------------------------

    summary_file = os.path.join(
        output_dir,
        "summary.json",
    )

    with open(
        summary_file,
        mode="w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary_data,
            f,
            indent=2,
        )

    print("=" * 80)
    print("BATCH EXECUTION SUMMARY")
    print("=" * 80)
    print(
        f"Total Cases: {total_count}"
    )
    print(
        f"Completed:   {completed_count}"
    )
    print(
        f"Failed:      {failed_count}"
    )
    print(
        f"Runtime:     {total_time}s"
    )
    print(
        f"Verdicts:    {verdict_counts}"
    )
    print(
        f"Actions:     {action_counts}"
    )
    print(
        f"Summary saved to: {summary_file}"
    )
    print("=" * 80)

    return summary_data


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

if __name__ == "__main__":

    summary = run_all_cases()

    if summary.get(
        "failed",
        0,
    ) > 0:

        sys.exit(1)

    sys.exit(0)