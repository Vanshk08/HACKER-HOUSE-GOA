"""
Unit tests auditing policy correctness and customer response status rules.
Regression tests specifically verifying:
- test_pending_validation_is_not_denial
- test_pending_validation_is_not_confirmation
- test_pending_validation_is_not_no_response
- test_r2_requires_actual_denial
- test_r3_requires_actual_confirmation
- test_r4_requires_verified_24h_no_response
- test_r1_does_not_use_unauthorized_risk_score_threshold
- test_r1_uses_fraud_probability_threshold
- test_risk_score_is_not_fraud_probability
- test_batch_cases_without_customer_response_remain_unknown
- test_request_customer_validation_does_not_modify_status
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.state import create_initial_state
from agent.tool_executor import ToolExecutor
from config.policy import (
    extract_policy_context,
    evaluate_policy,
    rule_r1,
    rule_r2,
    rule_r3,
    rule_r4,
)
from run_all import load_cases
from tools.evidence_requests import request_customer_validation


class TestPolicyAudit(unittest.TestCase):
    """Regression test suite for customer response status and policy determinism."""

    def test_pending_validation_is_not_denial(self):
        """A pending customer validation request must not be converted into 'denied'."""
        state = create_initial_state(
            case_id="TEST-001",
            customer_id="C00001",
            card_id="C00001-K1",
            flagged_txn_id="1000001",
            trigger_type="customer_report",
            trigger_text="Customer message: 'I never made this purchase.'",
        )
        state["evidence_requests"] = [
            {
                "request_type": "customer_confirmation",
                "transaction_id": "1000001",
                "status": "pending",
            }
        ]
        context = extract_policy_context(state)
        self.assertEqual(context["customer_response_status"], "unknown")
        self.assertNotEqual(context["customer_response_status"], "denied")

    def test_pending_validation_is_not_confirmation(self):
        """A pending customer validation request must not be converted into 'confirmed'."""
        state = create_initial_state(
            case_id="TEST-002",
            customer_id="C00002",
            card_id="C00002-K1",
            flagged_txn_id="1000002",
            trigger_type="risk_score",
            risk_score=0.65,
        )
        state["evidence_requests"] = [
            {
                "request_type": "customer_confirmation",
                "transaction_id": "1000002",
                "status": "pending",
            }
        ]
        context = extract_policy_context(state)
        self.assertEqual(context["customer_response_status"], "unknown")
        self.assertNotEqual(context["customer_response_status"], "confirmed")

    def test_pending_validation_is_not_no_response(self):
        """A pending customer validation request must not be converted into 'no_response' unless 24h elapsed."""
        state = create_initial_state(
            case_id="TEST-003",
            customer_id="C00003",
            card_id="C00003-K1",
            flagged_txn_id="1000003",
        )
        state["evidence_requests"] = [
            {
                "request_type": "customer_confirmation",
                "transaction_id": "1000003",
                "status": "pending",
            }
        ]
        state["hours_since_outreach"] = 2.0  # only 2 hours elapsed
        context = extract_policy_context(state)
        self.assertEqual(context["customer_response_status"], "unknown")
        self.assertNotEqual(context["customer_response_status"], "no_response")

    def test_r2_requires_actual_denial(self):
        """Rule R2 must NOT trigger when customer_response_status is 'unknown', only when 'denied'."""
        # Case with unknown status (should NOT match R2)
        ctx_unknown = {
            "case_id": "TEST-004",
            "customer_response_status": "unknown",
            "exposure": 128.33,
            "verdict": "uncertain",
            "fraud_probability": 0.52,
        }
        res_unknown = rule_r2(ctx_unknown)
        self.assertFalse(res_unknown.matched, "R2 must not match when customer response is unknown")
        self.assertNotIn("BLOCK_CARD", res_unknown.actions)

        # Case with actual verified denial (MUST match R2)
        ctx_denied = {
            "case_id": "TEST-004B",
            "customer_response_status": "denied",
            "exposure": 128.33,
            "verdict": "confirmed_fraud",
            "fraud_probability": 0.92,
        }
        res_denied = rule_r2(ctx_denied)
        self.assertTrue(res_denied.matched, "R2 must match when customer response is denied")
        self.assertIn("BLOCK_CARD", res_denied.actions)
        self.assertIn("CREATE_CASE", res_denied.actions)

    def test_r3_requires_actual_confirmation(self):
        """Rule R3 must NOT trigger when customer_response_status is 'unknown', only when 'confirmed'."""
        # Case with unknown status (should NOT match R3)
        ctx_unknown = {
            "case_id": "TEST-005",
            "customer_response_status": "unknown",
            "verdict": "uncertain",
            "fraud_probability": 0.42,
        }
        res_unknown = rule_r3(ctx_unknown)
        self.assertFalse(res_unknown.matched, "R3 must not match when customer response is unknown")
        self.assertNotIn("CLOSE_NO_FRAUD", res_unknown.actions)

        # Case with actual confirmation (MUST match R3)
        ctx_confirmed = {
            "case_id": "TEST-005B",
            "customer_response_status": "confirmed",
            "verdict": "legitimate",
            "fraud_probability": 0.05,
        }
        res_confirmed = rule_r3(ctx_confirmed)
        self.assertTrue(res_confirmed.matched, "R3 must match when customer response is confirmed")
        self.assertIn("CLOSE_NO_FRAUD", res_confirmed.actions)

    def test_r4_requires_verified_24h_no_response(self):
        """Rule R4 must NOT trigger for pending validation requests unless 24 hours have actually elapsed."""
        # Pending request with < 24 hours elapsed
        ctx_recent = {
            "case_id": "TEST-006",
            "customer_response_status": "unknown",
            "hours_since_outreach": 5.5,
            "exposure": 200.0,
        }
        res_recent = rule_r4(ctx_recent)
        self.assertFalse(res_recent.matched, "R4 must not match when under 24 hours")

        # Verified 24h elapsed
        ctx_24h = {
            "case_id": "TEST-006B",
            "customer_response_status": "no_response",
            "hours_since_outreach": 24.5,
            "exposure": 600.0,
        }
        res_24h = rule_r4(ctx_24h)
        self.assertTrue(res_24h.matched, "R4 must match after 24h of no response")
        self.assertIn("MONITOR_CARD", res_24h.actions)
        self.assertIn("DECLINE_TRANSACTION", res_24h.actions)
        self.assertIn("ESCALATE_TO_ANALYST", res_24h.actions)  # exposure > $500

    def test_r1_does_not_use_unauthorized_risk_score_threshold(self):
        """Rule R1 must NOT require an unauthorized risk score threshold such as > 0.40 or > 0.50."""
        # Case with very low initial risk score (0.15), but fraud probability < 0.70
        ctx_low_risk = {
            "case_id": "TEST-007",
            "verdict": "uncertain",
            "fraud_probability": 0.45,
            "risk_score": 0.15,  # Well below 0.40
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res = rule_r1(ctx_low_risk)
        self.assertTrue(res.matched, "R1 must match based on fraud_probability < 0.70, not risk_score > 0.40")
        self.assertIn("STEP_UP_AUTH", res.actions)

    def test_r1_uses_fraud_probability_threshold(self):
        """Rule R1 strictly applies fraud_probability < 0.70 threshold."""
        # fraud_probability = 0.69 -> Matches R1
        ctx_under = {
            "verdict": "uncertain",
            "fraud_probability": 0.69,
            "risk_score": 0.60,
            "channel": "in_person",
            "customer_response_status": "unknown",
        }
        res_under = rule_r1(ctx_under)
        self.assertTrue(res_under.matched)
        self.assertIn("VERIFY_WITH_CUSTOMER", res_under.actions)

        # fraud_probability = 0.70 -> Does not match R1
        ctx_at = {
            "verdict": "uncertain",
            "fraud_probability": 0.70,
            "risk_score": 0.60,
            "channel": "in_person",
            "customer_response_status": "unknown",
        }
        res_at = rule_r1(ctx_at)
        self.assertFalse(res_at.matched, "R1 must not match when fraud_probability >= 0.70")

        # fraud_probability = 0.85 -> Does not match R1
        ctx_above = {
            "verdict": "suspected_fraud",
            "fraud_probability": 0.85,
            "risk_score": 0.60,
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_above = rule_r1(ctx_above)
        self.assertFalse(res_above.matched, "R1 must not match when fraud_probability >= 0.70")

    def test_r1_single_signal_requirements(self):
        """
        Comprehensive test for R1 single-signal requirements:
        8a: risk_score-only unresolved case with prob < 0.70 -> matches R1
        8b: multiple independent corroborating sources with prob < 0.70 -> does NOT match R1
        8c: customer response resolved ('confirmed' or 'denied') -> does NOT match R1
        8d: prob >= 0.70 -> does NOT match R1
        """
        # 8a: risk_score-only unresolved case
        ctx_8a = {
            "verdict": "uncertain",
            "fraud_probability": 0.45,
            "risk_score": 0.65,
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_8a = rule_r1(ctx_8a)
        self.assertTrue(res_8a.matched, "8a: risk_score-only unresolved case must match R1")
        self.assertIn("STEP_UP_AUTH", res_8a.actions)

        # 8b: multiple independent corroborating sources
        ctx_8b_sources = {
            "verdict": "uncertain",
            "fraud_probability": 0.45,
            "risk_score": 0.65,
            "independent_evidence_sources": ["risk_score", "device_fingerprint_anomaly"],
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_8b_sources = rule_r1(ctx_8b_sources)
        self.assertFalse(
            res_8b_sources.matched,
            "8b: multiple independent corroborating sources must NOT match R1",
        )

        ctx_8b_clusters = {
            "verdict": "uncertain",
            "fraud_probability": 0.45,
            "risk_score": 0.65,
            "has_shared_device_fraud_cluster": True,
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_8b_clusters = rule_r1(ctx_8b_clusters)
        self.assertFalse(
            res_8b_clusters.matched,
            "8b: multiple active fraud signals must NOT match R1",
        )

        # 8c: customer response resolved
        ctx_8c_confirmed = {
            "verdict": "uncertain",
            "fraud_probability": 0.45,
            "risk_score": 0.65,
            "channel": "online",
            "customer_response_status": "confirmed",
        }
        self.assertFalse(rule_r1(ctx_8c_confirmed).matched, "8c: confirmed status must NOT match R1")

        ctx_8c_denied = {
            "verdict": "uncertain",
            "fraud_probability": 0.45,
            "risk_score": 0.65,
            "channel": "online",
            "customer_response_status": "denied",
        }
        self.assertFalse(rule_r1(ctx_8c_denied).matched, "8c: denied status must NOT match R1")

        # 8d: prob >= 0.70
        ctx_8d = {
            "verdict": "suspected_fraud",
            "fraud_probability": 0.75,
            "risk_score": 0.85,
            "channel": "online",
            "customer_response_status": "unknown",
        }
        self.assertFalse(rule_r1(ctx_8d).matched, "8d: prob >= 0.70 must NOT match R1")

    def test_r1_hhg001_legitimate_multiple_sources_regression(self):
        """
        Requirement 9: Regression test for HHG-001's situation.
        verdict='legitimate', fraud_probability=0.05, multiple independent evidence sources, customer_response_status='unknown'.
        Verify R1 does NOT match merely because 0.05 < 0.70.
        """
        ctx_hhg001 = {
            "case_id": "HHG-001",
            "verdict": "legitimate",
            "fraud_probability": 0.05,
            "independent_evidence_sources": [
                "customer_regional_history",
                "spend_amount_consistency",
                "in_person_routine_channel",
                "isolated_device_profile",
            ],
            "contradicting_evidence": [
                "15 prior transactions in region 444 totaling $1,049.26.",
                "Amount of $77.07 aligns with prior purchases ($76.96-$77.05).",
                "Transaction channel was in-person.",
                "No shared devices across customer network.",
            ],
            "channel": "in_person",
            "customer_response_status": "unknown",
            "risk_score": 0.61,
        }
        res = rule_r1(ctx_hhg001)
        self.assertFalse(
            res.matched,
            "R1 must NOT match for HHG-001 legitimate case merely because 0.05 < 0.70",
        )
        self.assertEqual(res.actions, [])

        decision = evaluate_policy(ctx_hhg001)
        self.assertNotIn("R1", decision["matched_rules"])
        self.assertNotIn("VERIFY_WITH_CUSTOMER", decision["actions"])

    def test_risk_score_is_not_fraud_probability(self):
        """Initial trigger risk_score is an input signal, not the evaluated fraud_probability."""
        # Case where initial model scored 0.90, but investigation evaluated fraud_probability to 0.42
        ctx = {
            "case_id": "TEST-009",
            "verdict": "uncertain",
            "fraud_probability": 0.42,
            "risk_score": 0.90,
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_r1 = rule_r1(ctx)
        # Must evaluate against fraud_probability (0.42 < 0.70), matching R1
        self.assertTrue(res_r1.matched)
        self.assertIn("STEP_UP_AUTH", res_r1.actions)

    def test_batch_cases_without_customer_response_remain_unknown(self):
        """All cases in data/case_pack.csv lack customer response and must initialize to 'unknown'."""
        cases = load_cases("data/case_pack.csv")
        self.assertEqual(len(cases), 20)

        for case_info in cases:
            state = create_initial_state(
                case_id=case_info["case_id"],
                customer_id=case_info["customer_id"],
                card_id=case_info["card_id"],
                flagged_txn_id=case_info["flagged_txn_id"],
                trigger_type=case_info.get("trigger_type"),
                trigger_text=case_info.get("trigger_text"),
                risk_score=case_info.get("risk_score"),
            )
            self.assertEqual(
                state["customer_response_status"],
                "unknown",
                f"Case {case_info['case_id']} customer_response_status must be 'unknown', got '{state['customer_response_status']}'"
            )

    def test_request_customer_validation_does_not_modify_customer_response_status(self):
        """Executing request_customer_validation() must NOT alter customer_response_status from 'unknown'."""
        executor = ToolExecutor()
        initial_state = create_initial_state(
            case_id="TEST-010",
            customer_id="C12382",
            card_id="C12382-K1",
            flagged_txn_id="3514030",
        )
        self.assertEqual(initial_state["customer_response_status"], "unknown")

        tool_call = {
            "name": "request_customer_validation",
            "args": {
                "transaction_id": "3514030",
                "question": "Did you authorize this transaction?",
            },
            "id": "call_test_val",
        }

        # Simulate state update through ToolExecutor.node
        from langchain_core.messages import AIMessage
        initial_state["messages"] = [AIMessage(content="Need validation", tool_calls=[tool_call])]
        updates = executor.node(initial_state)

        # Merge updates
        for k, v in updates.items():
            initial_state[k] = v

        # customer_response_status must remain 'unknown'
        self.assertEqual(
            initial_state["customer_response_status"],
            "unknown",
            "request_customer_validation must not mutate customer_response_status to confirmed or denied"
        )
        # Verify evidence_requests received the pending request descriptor
        self.assertEqual(len(initial_state["evidence_requests"]), 1)
        self.assertEqual(initial_state["evidence_requests"][0]["status"], "pending")

    def test_legitimate_no_customer_confirmation_no_close_no_fraud(self):
        """
        6a: A legitimate verdict with probability <= 0.15 does NOT automatically mean CLOSE_NO_FRAUD.
        R3 requires customer confirmation. If investigation has not received customer confirmation,
        agent/policy must not produce CLOSE_NO_FRAUD, must set exposure=0, affected_txn_ids=[],
        and must record a customer validation request in evidence_requests.
        """
        state = create_initial_state(
            case_id="HHG-001",
            customer_id="C12382",
            card_id="C12382-K1",
            flagged_txn_id="3514030",
            trigger_type="risk_score",
            trigger_text="Model scored 0.61",
            risk_score=0.61,
        )
        state["customer_response_status"] = "unknown"
        state["assessment"] = {
            "verdict": "legitimate",
            "fraud_probability": 0.05,
            "fraud_type": None,
            "exposure": 0.0,
            "affected_txn_ids": [],
            "supporting_evidence": ["15 prior transactions in region 444"],
            "contradicting_evidence": [],
            "reasoning": "Transaction matches legitimate cardholder behavior.",
            "confidence": 0.90,
        }
        state["evidence"] = [
            {
                "source": "get_transaction",
                "data": {"arguments": {"transaction_id": "3514030"}, "result": {"amount": 77.07, "channel": "in_person"}},
            }
        ]

        decision = evaluate_policy(state)

        # Invariants:
        # 1. No CLOSE_NO_FRAUD without customer confirmation
        self.assertNotIn("CLOSE_NO_FRAUD", decision["actions"])
        # 2. No action invented merely because verdict is legitimate
        self.assertEqual(decision["actions"], [])
        self.assertEqual(decision["matched_rules"], [])
        # 3. Legitimate cases have exposure 0 and affected_txn_ids = []
        self.assertEqual(decision["exposure"], 0.0)
        self.assertEqual(decision["affected_txn_ids"], [])
        # 4. Customer validation request recorded in evidence_requests
        self.assertTrue(len(decision["evidence_requests"]) >= 1)
        cust_req = next(
            (r for r in decision["evidence_requests"] if r.get("request_type") == "customer_confirmation"),
            None,
        )
        self.assertIsNotNone(cust_req)
        self.assertEqual(cust_req["status"], "pending")
        self.assertEqual(str(cust_req["transaction_id"]), "3514030")

    def test_legitimate_confirmed_customer_close_no_fraud(self):
        """
        6b: When the verdict is legitimate AND the customer has confirmed authorization,
        Rule R3 MUST match and produce CLOSE_NO_FRAUD.
        """
        state = create_initial_state(
            case_id="HHG-001",
            customer_id="C12382",
            card_id="C12382-K1",
            flagged_txn_id="3514030",
        )
        state["customer_response_status"] = "confirmed"
        state["customer_confirmed"] = True
        state["assessment"] = {
            "verdict": "legitimate",
            "fraud_probability": 0.05,
            "fraud_type": None,
            "exposure": 0.0,
            "affected_txn_ids": [],
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "reasoning": "Customer confirmed transaction.",
            "confidence": 0.95,
        }

        decision = evaluate_policy(state)

        self.assertIn("R3", decision["matched_rules"])
        self.assertEqual(decision["actions"], ["CLOSE_NO_FRAUD"])
        self.assertEqual(decision["primary_action"], "CLOSE_NO_FRAUD")
        self.assertEqual(decision["exposure"], 0.0)
        self.assertEqual(decision["affected_txn_ids"], [])

    def test_uncertain_case_policy_actions_follow_readme(self):
        """
        6c: An uncertain case with unconfirmed risk (fraud_probability < 0.70)
        must trigger R1 (VERIFY_WITH_CUSTOMER or STEP_UP_AUTH) and GLOBAL_CREATE_CASE (if prob >= 0.30),
        maintain its non-zero exposure and affected_txn_ids, and never CLOSE_NO_FRAUD.
        """
        state = create_initial_state(
            case_id="HHG-001",
            customer_id="C12382",
            card_id="C12382-K1",
            flagged_txn_id="3514030",
            trigger_type="risk_score",
            risk_score=0.61,
        )
        state["customer_response_status"] = "unknown"
        state["channel"] = "in_person"
        state["assessment"] = {
            "verdict": "uncertain",
            "fraud_probability": 0.42,
            "fraud_type": None,
            "exposure": 77.07,
            "affected_txn_ids": ["3514030"],
            "supporting_evidence": ["Risk score 0.61"],
            "contradicting_evidence": [],
            "reasoning": "Uncertain pending customer outreach.",
            "confidence": 0.60,
        }

        decision = evaluate_policy(state)

        self.assertIn("R1", decision["matched_rules"])
        self.assertIn("GLOBAL_CREATE_CASE", decision["matched_rules"])
        self.assertIn("VERIFY_WITH_CUSTOMER", decision["actions"])
        self.assertIn("CREATE_CASE", decision["actions"])
        self.assertNotIn("CLOSE_NO_FRAUD", decision["actions"])
        self.assertEqual(decision["exposure"], 77.07)
        self.assertEqual(decision["affected_txn_ids"], ["3514030"])


if __name__ == "__main__":
    unittest.main()

