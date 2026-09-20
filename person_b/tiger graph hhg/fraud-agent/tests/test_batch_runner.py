"""
Unit tests for the Batch Runner (run_all.py).
Verifies:
1. Discovery and uniqueness of all 20 cases from case_pack.csv.
2. State isolation and initial state independence.
3. Assessment schema validation.
4. Policy schema and action validation.
5. Cross-case evidence leakage detection.
6. Result file generation and summary structure.
7. Graceful continuation after individual case failure.
"""

import os
import sys
import tempfile
import shutil
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from run_all import load_cases, validate_case_execution, run_single_case, run_all_cases
from agent.state import create_initial_state


class MockTestGraph:
    """Fast deterministic mock graph for testing batch runner mechanics."""

    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def invoke(self, state):
        if self.should_fail and state["case_id"] == "FAIL-001":
            raise RuntimeError("Simulated failure on test case FAIL-001")

        return {
            "case_id": state["case_id"],
            "customer_id": state["customer_id"],
            "card_id": state["card_id"],
            "flagged_txn_id": state["flagged_txn_id"],
            "iteration_count": 3,
            "tools_used": ["get_transaction", "get_customer_regions"],
            "evidence": [
                {
                    "source": "get_transaction",
                    "type": "tool_result",
                    "confidence": 1.0,
                    "data": {
                        "arguments": {"transaction_id": state["flagged_txn_id"]},
                        "result": {"amount": 77.07},
                    },
                }
            ],
            "hypotheses": [
                {
                    "id": "h1",
                    "title": "Recurring Behavior",
                    "description": "Legitimate customer behavior",
                    "confidence": 0.6,
                    "supporting_evidence": ["Historical regions match"],
                    "contradicting_evidence": [],
                }
            ],
            "evidence_requests": [],
            "assessment": {
                "verdict": "uncertain",
                "fraud_probability": 0.42,
                "fraud_type": None,
                "exposure": 77.07,
                "affected_txn_ids": [state["flagged_txn_id"]],
                "supporting_evidence": ["Risk score 0.61"],
                "contradicting_evidence": ["Region 444 historical usage"],
                "reasoning": "Uncertain verdict pending customer validation.",
                "confidence": 0.62,
            },
            "policy_decision": {
                "actions": ["VERIFY_WITH_CUSTOMER", "CREATE_CASE"],
                "primary_action": "VERIFY_WITH_CUSTOMER",
                "matched_rules": ["R1", "GLOBAL_CREATE_CASE"],
                "rationale": "Policy decision reached.",
                "requires_customer_response": True,
                "evidence_requests": [],
                "exposure": 77.07,
                "affected_txn_ids": [state["flagged_txn_id"]],
                "customer_response_status": "unknown",
                "policy_conflicts": [],
            },
        }


class TestBatchRunner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="fraud_batch_test_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_case_discovery_and_uniqueness(self):
        """Verify all 20 case records are discovered and have unique identifiers."""
        cases = load_cases("data/case_pack.csv")
        self.assertEqual(len(cases), 20, "Expected exactly 20 cases from case_pack.csv")

        case_ids = [c["case_id"] for c in cases]
        self.assertEqual(len(case_ids), len(set(case_ids)), "Case IDs must be unique")

        # Verify required identifier fields
        for c in cases:
            self.assertTrue(c["case_id"].startswith("HHG-"), f"Invalid case ID: {c['case_id']}")
            self.assertTrue(c["customer_id"].startswith("C"), f"Invalid customer ID: {c['customer_id']}")
            self.assertTrue("-" in c["card_id"], f"Invalid card ID: {c['card_id']}")
            self.assertTrue(c["flagged_txn_id"].isdigit(), f"Invalid txn ID: {c['flagged_txn_id']}")

    def test_case_isolation_and_initial_state(self):
        """Verify each case creates a distinct and independent initial state."""
        state1 = create_initial_state("HHG-001", "C12382", "C12382-K1", "3514030")
        state2 = create_initial_state("HHG-002", "C11891", "C11891-K1", "3478782")

        self.assertNotEqual(state1["case_id"], state2["case_id"])
        self.assertNotEqual(state1["customer_id"], state2["customer_id"])

        # Mutating state1 must not leak into state2
        state1["evidence"].append({"source": "tool_1"})
        state1["tools_used"].append("tool_1")
        self.assertEqual(len(state2["evidence"]), 0)
        self.assertEqual(len(state2["tools_used"]), 0)

    def test_assessment_validation(self):
        """Verify validation checks catch malformed assessment outputs."""
        case_info = {"case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030"}

        # 1. Missing assessment
        state_bad_ass = {"case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030", "assessment": None}
        with self.assertRaises(ValueError):
            validate_case_execution(case_info, state_bad_ass)

        # 2. Invalid verdict
        state_bad_verdict = {
            "case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030",
            "assessment": {"verdict": "INVALID_VERDICT", "fraud_probability": 0.5, "exposure": 10.0, "affected_txn_ids": []},
            "policy_decision": {"actions": [], "matched_rules": [], "customer_response_status": "unknown"}
        }
        with self.assertRaises(ValueError):
            validate_case_execution(case_info, state_bad_verdict)

        # 3. Invalid probability (> 1.0)
        state_bad_prob = {
            "case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030",
            "assessment": {"verdict": "uncertain", "fraud_probability": 1.5, "exposure": 10.0, "affected_txn_ids": []},
            "policy_decision": {"actions": [], "matched_rules": [], "customer_response_status": "unknown"}
        }
        with self.assertRaises(ValueError):
            validate_case_execution(case_info, state_bad_prob)

    def test_policy_validation(self):
        """Verify validation checks catch invalid policy actions or rules."""
        case_info = {"case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030"}

        # Invalid policy action
        state_bad_action = {
            "case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030",
            "assessment": {"verdict": "uncertain", "fraud_probability": 0.4, "exposure": 10.0, "affected_txn_ids": []},
            "policy_decision": {"actions": ["INVALID_ACTION_123"], "matched_rules": ["R1"], "customer_response_status": "unknown"}
        }
        with self.assertRaises(ValueError):
            validate_case_execution(case_info, state_bad_action)

        # Invalid matched rule
        state_bad_rule = {
            "case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030",
            "assessment": {"verdict": "uncertain", "fraud_probability": 0.4, "exposure": 10.0, "affected_txn_ids": []},
            "policy_decision": {"actions": ["CREATE_CASE"], "matched_rules": ["RULE_XYZ"], "customer_response_status": "unknown"}
        }
        with self.assertRaises(ValueError):
            validate_case_execution(case_info, state_bad_rule)

    def test_cross_case_evidence_leakage_detection(self):
        """Verify that foreign customer evidence in state triggers a validation error."""
        case_info = {"case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030"}
        state_with_leakage = {
            "case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030",
            "assessment": {"verdict": "uncertain", "fraud_probability": 0.4, "exposure": 77.07, "affected_txn_ids": ["3514030"]},
            "policy_decision": {"actions": ["CREATE_CASE"], "matched_rules": ["GLOBAL_CREATE_CASE"], "customer_response_status": "unknown"},
            "evidence": [
                {
                    "source": "get_customer_history",
                    "data": {"arguments": {"customer_id": "C99999_FOREIGN_CUSTOMER"}},
                }
            ],
        }
        with self.assertRaises(ValueError) as cm:
            validate_case_execution(case_info, state_with_leakage)
        self.assertIn("Cross-case evidence leakage", str(cm.exception))

    def test_run_single_case_structure(self):
        """Verify single case execution writes expected JSON structure."""
        case_info = {
            "case_id": "HHG-001",
            "customer_id": "C12382",
            "card_id": "C12382-K1",
            "flagged_txn_id": "3514030",
            "trigger_type": "risk_score",
            "trigger_text": "Model scored 0.61",
            "risk_score": 0.61,
        }
        graph = MockTestGraph()
        record = run_single_case(case_info, graph=graph, output_dir=self.test_dir)

        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["case_id"], "HHG-001")
        self.assertIn("input", record)
        self.assertIn("investigation", record)
        self.assertIn("assessment", record)
        self.assertIn("policy", record)

        # Verify file on disk
        case_file = os.path.join(self.test_dir, "HHG-001.json")
        self.assertTrue(os.path.exists(case_file))

    def test_failed_cases_continue_execution(self):
        """Verify that if one case fails, subsequent cases continue running."""
        case_fail = {"case_id": "FAIL-001", "customer_id": "C00001", "card_id": "C00001-K1", "flagged_txn_id": "1000001"}
        case_pass = {"case_id": "PASS-002", "customer_id": "C00002", "card_id": "C00002-K1", "flagged_txn_id": "1000002"}

        graph = MockTestGraph(should_fail=True)

        rec_fail = run_single_case(case_fail, graph=graph, output_dir=self.test_dir)
        self.assertEqual(rec_fail["status"], "failed")
        self.assertIn("Simulated failure", rec_fail["error"])

        rec_pass = run_single_case(case_pass, graph=graph, output_dir=self.test_dir)
        self.assertEqual(rec_pass["status"], "completed")
        self.assertEqual(rec_pass["case_id"], "PASS-002")


if __name__ == "__main__":
    unittest.main()
