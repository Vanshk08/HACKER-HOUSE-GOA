"""
Authoritative README and Schema Validator for submission cases (cases/HHG-001.json - HHG-020.json).

Validates:
1. All 9 top-level required fields exist:
   - case_id (str)
   - case (dict)
   - evidence_requests (list)
   - next_best_actions (dict with initial & final lists of action objects)
   - sar (dict with file, reason, narrative, subjects, total_amount_usd, activity_dates)
   - stop_reason (str)
   - tool_calls (int)
   - tokens (int)
   - latency_s (float)
2. All 15 required case fields exist:
   - status (str)
   - verdict (str enum: confirmed_fraud | suspected_fraud | uncertain | legitimate)
   - fraud_probability (float, 0.0-1.0)
   - pattern (str enum: card_testing | card_not_present_fraud | card_not_present_new_device |
                        out_of_region_use | account_takeover | undocumented | none)
   - pattern_description (str)
   - affected_txn_ids (list[str])
   - first_suspicious_txn_id (str)
   - connected_card_ids (list[str])
   - connected_device_profiles (list[str])
   - exposure_usd (number >= 0)
   - evidence (list)
   - similar_prior_cases (list)
   - summary (str)
   - written_to_graph (bool)
   - graph_case_id (str)
3. next_best_actions.initial and .final contain objects {action, route, reason}, route in auto|L1|L2.
4. sar contains required fields. If FILE_REPORT is not in final actions: narrative="", subjects=[], amount=0, dates=[].
5. legitimate cases have affected_txn_ids=[] and exposure_usd=0.
6. tool_calls is an integer count.
7. tokens is an integer total.
8. latency_s is a float.
9. No nulls for required enum fields.
"""

import os
import sys
import json
import glob
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from schemas.output_adapter import VALID_PATTERNS, VALID_ROUTES

ALLOWED_VERDICTS = {"confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"}
REQUIRED_TOP_LEVEL = {
    "case_id",
    "case",
    "evidence_requests",
    "next_best_actions",
    "sar",
    "stop_reason",
    "tool_calls",
    "tokens",
    "latency_s",
}
REQUIRED_CASE_FIELDS = {
    "status",
    "verdict",
    "fraud_probability",
    "pattern",
    "pattern_description",
    "affected_txn_ids",
    "first_suspicious_txn_id",
    "connected_card_ids",
    "connected_device_profiles",
    "exposure_usd",
    "evidence",
    "similar_prior_cases",
    "summary",
    "written_to_graph",
    "graph_case_id",
}


def validate_case_file(fpath: str) -> list[str]:
    """Validates a single case file against all README specifications. Returns list of errors."""
    errors = []
    fname = os.path.basename(fpath)

    try:
        with open(fpath, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception as e:
        return [f"{fname}: Failed to load JSON: {e}"]

    # 1. Top-level fields
    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            errors.append(f"{fname}: Missing required top-level field '{field}'")

    if not isinstance(data.get("case_id"), str) or not data.get("case_id"):
        errors.append(f"{fname}: 'case_id' must be a non-empty string, got {type(data.get('case_id'))}")

    if not isinstance(data.get("tool_calls"), int) or isinstance(data.get("tool_calls"), bool):
        errors.append(f"{fname}: 'tool_calls' must be an integer count, got {type(data.get('tool_calls'))}")

    if not isinstance(data.get("tokens"), int) or isinstance(data.get("tokens"), bool):
        errors.append(f"{fname}: 'tokens' must be an integer count, got {type(data.get('tokens'))}")

    if not isinstance(data.get("latency_s"), (int, float)):
        errors.append(f"{fname}: 'latency_s' must be a float/number, got {type(data.get('latency_s'))}")

    if not isinstance(data.get("stop_reason"), str) or not data.get("stop_reason"):
        errors.append(f"{fname}: 'stop_reason' must be a non-empty string")

    if not isinstance(data.get("evidence_requests"), list):
        errors.append(f"{fname}: 'evidence_requests' must be a list")

    # 2. Case Object
    case_obj = data.get("case")
    if not isinstance(case_obj, dict):
        errors.append(f"{fname}: 'case' must be a dict")
        return errors

    for field in REQUIRED_CASE_FIELDS:
        if field not in case_obj:
            errors.append(f"{fname}: Missing required case field '{field}'")
        elif case_obj[field] is None:
            errors.append(f"{fname}: Required case field '{field}' cannot be null")

    verdict = case_obj.get("verdict")
    if verdict not in ALLOWED_VERDICTS:
        errors.append(f"{fname}: Invalid verdict '{verdict}', must be one of {ALLOWED_VERDICTS}")

    prob = case_obj.get("fraud_probability")
    if not isinstance(prob, (int, float)) or not (0.0 <= prob <= 1.0):
        errors.append(f"{fname}: 'fraud_probability' must be a float between 0.0 and 1.0, got {prob}")

    pattern = case_obj.get("pattern")
    if pattern not in VALID_PATTERNS:
        errors.append(f"{fname}: Invalid pattern '{pattern}', must be one of {VALID_PATTERNS}")

    if not isinstance(case_obj.get("pattern_description"), str):
        errors.append(f"{fname}: 'pattern_description' must be a string")

    affected_txns = case_obj.get("affected_txn_ids")
    if not isinstance(affected_txns, list):
        errors.append(f"{fname}: 'affected_txn_ids' must be a list")

    exposure = case_obj.get("exposure_usd")
    if not isinstance(exposure, (int, float)) or exposure < 0:
        errors.append(f"{fname}: 'exposure_usd' must be a non-negative number, got {exposure}")

    if verdict == "legitimate":
        if affected_txns != []:
            errors.append(f"{fname}: Legitimate case must have affected_txn_ids = [], got {affected_txns}")
        if exposure != 0.0:
            errors.append(f"{fname}: Legitimate case must have exposure_usd = 0, got {exposure}")
        if case_obj.get("first_suspicious_txn_id") != "":
            errors.append(f"{fname}: Legitimate case must have first_suspicious_txn_id = '', got {case_obj.get('first_suspicious_txn_id')}")

    if not isinstance(case_obj.get("first_suspicious_txn_id"), str):
        errors.append(f"{fname}: 'first_suspicious_txn_id' must be a string")

    if not isinstance(case_obj.get("connected_card_ids"), list):
        errors.append(f"{fname}: 'connected_card_ids' must be a list")

    if not isinstance(case_obj.get("connected_device_profiles"), list):
        errors.append(f"{fname}: 'connected_device_profiles' must be a list")

    if not isinstance(case_obj.get("evidence"), list):
        errors.append(f"{fname}: 'evidence' must be a list")

    if not isinstance(case_obj.get("similar_prior_cases"), list):
        errors.append(f"{fname}: 'similar_prior_cases' must be a list")

    if not isinstance(case_obj.get("summary"), str):
        errors.append(f"{fname}: 'summary' must be a string")

    if not isinstance(case_obj.get("written_to_graph"), bool):
        errors.append(f"{fname}: 'written_to_graph' must be a boolean, got {type(case_obj.get('written_to_graph'))}")

    if not isinstance(case_obj.get("graph_case_id"), str):
        errors.append(f"{fname}: 'graph_case_id' must be a string, got {type(case_obj.get('graph_case_id'))}")

    # 3. Next Best Actions
    nba = data.get("next_best_actions")
    if not isinstance(nba, dict):
        errors.append(f"{fname}: 'next_best_actions' must be a dict")
    else:
        for section in ("initial", "final"):
            items = nba.get(section)
            if not isinstance(items, list):
                errors.append(f"{fname}: next_best_actions.{section} must be a list")
            else:
                for idx, act in enumerate(items):
                    if not isinstance(act, dict):
                        errors.append(f"{fname}: next_best_actions.{section}[{idx}] must be a dict object")
                        continue
                    if "action" not in act or not isinstance(act["action"], str):
                        errors.append(f"{fname}: next_best_actions.{section}[{idx}] missing 'action' string")
                    route = act.get("route")
                    if route not in VALID_ROUTES:
                        errors.append(f"{fname}: next_best_actions.{section}[{idx}] route '{route}' not in {VALID_ROUTES}")
                    if "reason" not in act or not isinstance(act["reason"], str):
                        errors.append(f"{fname}: next_best_actions.{section}[{idx}] missing 'reason' string")

    # 4. SAR
    sar = data.get("sar")
    if not isinstance(sar, dict):
        errors.append(f"{fname}: 'sar' must be a dict")
    else:
        if not isinstance(sar.get("file"), bool):
            errors.append(f"{fname}: sar.file must be a boolean, got {type(sar.get('file'))}")
        if not isinstance(sar.get("reason"), str):
            errors.append(f"{fname}: sar.reason must be a string")
        if not isinstance(sar.get("narrative"), str):
            errors.append(f"{fname}: sar.narrative must be a string")
        if not isinstance(sar.get("subjects"), list):
            errors.append(f"{fname}: sar.subjects must be a list")
        if not isinstance(sar.get("total_amount_usd"), (int, float)):
            errors.append(f"{fname}: sar.total_amount_usd must be a number")
        if not isinstance(sar.get("activity_dates"), list):
            errors.append(f"{fname}: sar.activity_dates must be a list")

        final_actions = [a.get("action") for a in (nba.get("final") or []) if isinstance(a, dict)]
        if "FILE_REPORT" not in final_actions:
            if sar.get("narrative") != "":
                errors.append(f"{fname}: When FILE_REPORT not in final actions, sar.narrative must be empty, got '{sar.get('narrative')}'")
            if sar.get("subjects") != []:
                errors.append(f"{fname}: When FILE_REPORT not in final actions, sar.subjects must be [], got {sar.get('subjects')}")
            if sar.get("total_amount_usd") != 0.0:
                errors.append(f"{fname}: When FILE_REPORT not in final actions, sar.total_amount_usd must be 0, got {sar.get('total_amount_usd')}")
            if sar.get("activity_dates") != []:
                errors.append(f"{fname}: When FILE_REPORT not in final actions, sar.activity_dates must be [], got {sar.get('activity_dates')}")

    return errors


def validate_all_cases(cases_dir: str = "cases") -> bool:
    """Validates all 20 case files in cases_dir. Returns True if all pass, False otherwise."""
    cases_path = os.path.join(PROJECT_ROOT, cases_dir)
    file_pattern = os.path.join(cases_path, "HHG-*.json")
    files = sorted(glob.glob(file_pattern))

    print("=" * 80)
    print(f"README & SCHEMA VALIDATION: {len(files)} CASES IN {cases_path}")
    print("=" * 80)

    if len(files) != 20:
        print(f"WARNING: Expected exactly 20 case files, found {len(files)}.")

    all_passed = True
    total_errors = 0

    for fpath in files:
        fname = os.path.basename(fpath)
        errors = validate_case_file(fpath)
        if errors:
            all_passed = False
            total_errors += len(errors)
            print(f"[FAIL] {fname}:")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"[PASS] {fname}")

    print("=" * 80)
    if all_passed and len(files) == 20:
        print("ALL 20 CASES PASSED VALIDATION! 100% COMPLIANT WITH README SPECIFICATION.")
    else:
        print(f"VALIDATION FAILED with {total_errors} error(s).")
    print("=" * 80)

    return all_passed and len(files) == 20


if __name__ == "__main__":
    success = validate_all_cases()
    sys.exit(0 if success else 1)
