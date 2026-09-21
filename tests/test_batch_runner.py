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
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from run_all import load_cases, validate_case_execution, run_single_case, run_all_cases
from agent.state import create_initial_state


class MockTestGraph:
    """Fast deterministic mock graph for testing batch runner mechanics."""

    def __init__(self, should_fail=False, verdict="uncertain"):
        self.should_fail = should_fail
        self.verdict = verdict

    def invoke(self, state):
        if self.should_fail and state["case_id"] == "FAIL-001":
            raise RuntimeError("Simulated failure on test case FAIL-001")

        if self.verdict == "legitimate":
            return {
                "case_id": state["case_id"],
                "customer_id": state["customer_id"],
                "card_id": state["card_id"],
                "flagged_txn_id": state["flagged_txn_id"],
                "iteration_count": 4,
                "tools_used": ["get_transaction", "get_customer_regions"],
                "evidence": [
                    {
                        "source": "get_transaction",
                        "type": "tool_result",
                        "confidence": 1.0,
                        "data": {
                            "arguments": {"transaction_id": state["flagged_txn_id"]},
                            "result": {"amount": 77.07, "channel": "in_person"},
                        },
                    }
                ],
                "hypotheses": [
                    {
                        "id": "h1",
                        "title": "Routine legitimate cardholder spend",
                        "description": "Consistent with historical regional activity",
                        "confidence": 0.95,
                        "supporting_evidence": ["15 prior transactions in region 444"],
                        "contradicting_evidence": [],
                    }
                ],
                "evidence_requests": [],
                "assessment": {
                    "verdict": "legitimate",
                    "fraud_probability": 0.05,
                    "fraud_type": None,
                    "exposure": 0.0,
                    "affected_txn_ids": [],
                    "supporting_evidence": ["15 prior transactions in region 444 totaling $1,049.26"],
                    "contradicting_evidence": [],
                    "reasoning": "Transaction aligns with cardholder routine patterns.",
                    "confidence": 0.95,
                },
                "policy_decision": {
                    "actions": [],
                    "primary_action": None,
                    "matched_rules": [],
                    "rationale": "Policy evaluation completed.",
                    "requires_customer_response": True,
                    "evidence_requests": [
                        {
                            "request_id": f"req_cust_{state['flagged_txn_id']}",
                            "request_type": "customer_confirmation",
                            "transaction_id": state["flagged_txn_id"],
                            "question": f"Did you authorize transaction {state['flagged_txn_id']}?",
                            "status": "pending",
                        }
                    ],
                    "exposure": 0.0,
                    "affected_txn_ids": [],
                    "customer_response_status": "unknown",
                    "policy_conflicts": [],
                },
            }

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

    @patch("run_all.run_single_case")
    @patch("run_all.build_investigation_graph")
    def test_run_all_cases_single_case_filter(self, mock_build_graph, mock_run_single):
        """Verify run_all_cases with case_id runs only that case and updates summary."""
        mock_run_single.return_value = {
            "case_id": "HHG-001",
            "status": "completed",
            "runtime_seconds": 0.05,
            "latency_ms": 50.0,
            "assessment": {
                "verdict": "uncertain",
                "fraud_probability": 0.42,
                "fraud_type": None,
                "exposure": 77.07,
                "affected_txn_ids": ["3514030"],
            },
            "policy": {
                "actions": ["VERIFY_WITH_CUSTOMER", "CREATE_CASE"],
                "matched_rules": ["R1", "GLOBAL_CREATE_CASE"],
            },
            "investigation": {
                "tools_used": ["get_transaction"],
                "evidence_count": 1,
                "iteration_count": 1,
            },
            "errors": [],
        }

        out_dir = tempfile.mkdtemp(prefix="single_case_test_")
        try:
            summary = run_all_cases(output_dir=out_dir, provider="mock", case_id="HHG-001")
            self.assertEqual(summary["total_cases"], 1)
            self.assertEqual(summary["completed"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(len(summary["cases"]), 1)
            self.assertEqual(summary["cases"][0]["case_id"], "HHG-001")
            mock_run_single.assert_called_once()
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_run_all_cases_invalid_case_id_raises(self):
        """Verify run_all_cases raises clear ValueError when case_id not found."""
        with self.assertRaises(ValueError) as cm:
            run_all_cases(output_dir=self.test_dir, provider="mock", case_id="HHG-999")
        self.assertEqual(str(cm.exception), "Case ID HHG-999 not found in case_pack.csv")

    @patch("run_all.run_single_case")
    @patch("run_all.build_investigation_graph")
    def test_run_all_cases_omitted_case_id_preserves_all(self, mock_build_graph, mock_run_single):
        """Verify run_all_cases without case_id processes all 20 cases."""
        mock_run_single.return_value = {
            "case_id": "MOCK",
            "status": "completed",
            "runtime_seconds": 0.01,
            "latency_ms": 10.0,
            "assessment": {"verdict": "uncertain", "fraud_probability": 0.5, "affected_txn_ids": []},
            "policy": {"actions": ["CREATE_CASE"], "matched_rules": ["R1"]},
            "investigation": {"tools_used": [], "evidence_count": 0, "iteration_count": 1},
            "errors": [],
        }
        out_dir = tempfile.mkdtemp(prefix="all_cases_test_")
        try:
            summary = run_all_cases(output_dir=out_dir, provider="mock")
            self.assertEqual(summary["total_cases"], 20)
            self.assertEqual(mock_run_single.call_count, 20)
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_readme_output_schema_contract(self):
        """
        6d: Audits and verifies the complete serialized output schema contract
        against README requirements for both uncertain and legitimate cases.
        """
        out_dir = tempfile.mkdtemp(prefix="contract_schema_test_")
        try:
            # 1. Test Uncertain Case Output Contract
            case_uncertain = {
                "case_id": "HHG-001",
                "customer_id": "C12382",
                "card_id": "C12382-K1",
                "flagged_txn_id": "3514030",
                "trigger_type": "risk_score",
                "trigger_text": "Model scored 0.61",
                "risk_score": 0.61,
            }
            graph_unc = MockTestGraph(verdict="uncertain")
            rec_unc = run_single_case(case_uncertain, graph=graph_unc, output_dir=out_dir)

            # Required top-level keys
            required_top_level = {
                "case",
                "evidence_requests",
                "next_best_actions",
                "sar",
                "stop_reason",
                "tool_calls",
                "tokens",
                "latency",
            }
            for k in required_top_level:
                self.assertIn(k, rec_unc, f"Missing README top-level key: {k}")

            # Case object validation
            case_obj = rec_unc["case"]
            self.assertEqual(case_obj["case_id"], "HHG-001")
            self.assertEqual(case_obj["customer_id"], "C12382")
            self.assertEqual(case_obj["card_id"], "C12382-K1")
            self.assertEqual(case_obj["flagged_txn_id"], "3514030")
            self.assertEqual(case_obj["verdict"], "uncertain")
            self.assertEqual(case_obj["fraud_probability"], 0.42)
            self.assertEqual(case_obj["exposure_usd"], 77.07)
            self.assertEqual(case_obj["affected_txn_ids"], ["3514030"])

            # Next Best Actions validation
            nba = rec_unc["next_best_actions"]
            self.assertIn("initial", nba)
            self.assertIn("final", nba)
            self.assertIsInstance(nba["initial"], list)
            self.assertIsInstance(nba["final"], list)
            self.assertTrue(len(nba["initial"]) > 0)
            self.assertIn("VERIFY_WITH_CUSTOMER", nba["final"])
            self.assertIn("CREATE_CASE", nba["final"])

            # SAR validation
            sar = rec_unc["sar"]
            self.assertIn("file", sar)
            self.assertIn("reasons", sar)
            self.assertIsInstance(sar["file"], bool)
            self.assertIsInstance(sar["reasons"], list)

            # Tool calls & Latency validation
            self.assertIsInstance(rec_unc["tool_calls"], list)
            self.assertTrue(len(rec_unc["tool_calls"]) > 0)
            self.assertIn("tool", rec_unc["tool_calls"][0])
            self.assertIn("args", rec_unc["tool_calls"][0])
            self.assertIn("seconds", rec_unc["latency"])
            self.assertIn("ms", rec_unc["latency"])

            # 2. Test Legitimate Case Output Contract (HHG-001 regression)
            graph_leg = MockTestGraph(verdict="legitimate")
            rec_leg = run_single_case(case_uncertain, graph=graph_leg, output_dir=out_dir)

            case_leg = rec_leg["case"]
            self.assertEqual(case_leg["verdict"], "legitimate")
            # Invariant: legitimate cases have affected_txn_ids = []
            self.assertEqual(case_leg["affected_txn_ids"], [])
            # Invariant: legitimate cases have exposure_usd = 0
            self.assertEqual(case_leg["exposure_usd"], 0.0)
            # Invariant: legitimate cases have sar.file = false
            self.assertFalse(rec_leg["sar"]["file"])
            # Invariant: no CLOSE_NO_FRAUD without customer confirmation
            self.assertNotIn("CLOSE_NO_FRAUD", rec_leg["next_best_actions"]["final"])
            # Invariant: no action invented merely because verdict is legitimate
            self.assertEqual(rec_leg["next_best_actions"]["final"], [])
            # Invariant: customer validation request recorded in evidence_requests with assumptions
            self.assertTrue(len(rec_leg["evidence_requests"]) >= 1)
            leg_req = rec_leg["evidence_requests"][0]
            self.assertEqual(leg_req["request_type"], "customer_confirmation")
            self.assertEqual(leg_req["status"], "pending")
            self.assertEqual(leg_req["customer_response_status"], "unknown")
            self.assertIn("metadata", leg_req)
            self.assertIn("simulated_customer_response", leg_req["metadata"])

            # 3. Verify JSON file on disk adheres to the schema
            disk_file = os.path.join(out_dir, "HHG-001.json")
            self.assertTrue(os.path.exists(disk_file))
            with open(disk_file, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
            for k in required_top_level:
                self.assertIn(k, disk_data)

        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

