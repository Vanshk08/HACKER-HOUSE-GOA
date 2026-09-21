"""
Unit tests for the Policy Engine (config/policy.py and schemas/decision.py).
Tests all rules R1-R10, global mandatory rules, customer response states,
and conflict resolution.
"""

import os
import sys
import unittest

# Ensure fraud-agent is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.policy import (
    evaluate_policy,
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
)
from schemas.decision import VALID_ACTIONS


class TestPolicyRules(unittest.TestCase):
    """Test suite verifying each R1-R10 policy rule independently."""

    # ----------------------------------------------------
    # R1: Weak Single Signal
    # ----------------------------------------------------
    def test_r1_weak_signal(self):
        """Weak single signal, including risk score alone, AND fraud probability < 0.70."""
        # 8a: In-person transaction with risk score alone, fraud probability 0.42 -> matches R1
        ctx = {
            "verdict": "uncertain",
            "fraud_probability": 0.42,
            "risk_score": 0.61,
            "channel": "in_person",
            "customer_response_status": "unknown",
        }
        res = rule_r1(ctx)
        self.assertTrue(res.matched)
        self.assertIn("VERIFY_WITH_CUSTOMER", res.actions)
        self.assertNotIn("BLOCK_CARD", res.actions)

        # 8a: Online transaction with risk score alone, fraud probability 0.55 -> matches R1
        ctx_online = {
            "verdict": "uncertain",
            "fraud_probability": 0.55,
            "risk_score": 0.68,
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_online = rule_r1(ctx_online)
        self.assertTrue(res_online.matched)
        self.assertIn("STEP_UP_AUTH", res_online.actions)
        self.assertNotIn("BLOCK_CARD", res_online.actions)

        # 8b: Multiple independent corroborating sources with prob < 0.70 -> does NOT match R1
        ctx_multi_sources = {
            "verdict": "uncertain",
            "fraud_probability": 0.55,
            "risk_score": 0.68,
            "independent_evidence_sources": [
                "risk_score_model",
                "device_telemetry_anomaly",
            ],
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_multi_sources = rule_r1(ctx_multi_sources)
        self.assertFalse(
            res_multi_sources.matched,
            "R1 must not match when multiple independent corroborating sources exist",
        )

        ctx_multi_signals = {
            "verdict": "uncertain",
            "fraud_probability": 0.60,
            "risk_score": 0.65,
            "has_shared_device_fraud_cluster": True,
            "channel": "online",
            "customer_response_status": "unknown",
        }
        res_multi_signals = rule_r1(ctx_multi_signals)
        self.assertFalse(
            res_multi_signals.matched,
            "R1 must not match when multiple signals corroborate fraud",
        )

        # 8c: Customer response resolved ('confirmed' or 'denied') -> does NOT match R1
        ctx_confirmed = {
            "verdict": "uncertain",
            "fraud_probability": 0.42,
            "risk_score": 0.61,
            "channel": "in_person",
            "customer_response_status": "confirmed",
        }
        res_confirmed = rule_r1(ctx_confirmed)
        self.assertFalse(
            res_confirmed.matched,
            "R1 must not match when customer response is confirmed",
        )

        ctx_denied = {
            "verdict": "uncertain",
            "fraud_probability": 0.42,
            "risk_score": 0.61,
            "channel": "in_person",
            "customer_response_status": "denied",
        }
        res_denied = rule_r1(ctx_denied)
        self.assertFalse(
            res_denied.matched,
            "R1 must not match when customer response is denied",
        )

        # 8d: High probability (>= 0.70) does NOT match R1
        ctx_high = {
            "verdict": "suspected_fraud",
            "fraud_probability": 0.78,
            "risk_score": 0.82,
            "customer_response_status": "unknown",
        }
        res_high = rule_r1(ctx_high)
        self.assertFalse(res_high.matched, "R1 must not match when fraud_probability >= 0.70")

        ctx_boundary = {
            "verdict": "uncertain",
            "fraud_probability": 0.70,
            "risk_score": 0.65,
            "customer_response_status": "unknown",
        }
        res_boundary = rule_r1(ctx_boundary)
        self.assertFalse(res_boundary.matched, "R1 must not match when fraud_probability == 0.70")

    def test_r1_hhg001_legitimate_regression(self):
        """
        Requirement 9: Regression test for HHG-001's situation.
        verdict="legitimate", fraud_probability=0.05, multiple independent evidence sources, customer_response_status="unknown".
        Verify R1 does NOT match merely because 0.05 < 0.70.
        """
        ctx_hhg001 = {
            "case_id": "HHG-001",
            "verdict": "legitimate",
            "fraud_probability": 0.05,
            "independent_evidence_sources": [
                "customer_regional_history_15_prior_txns_region_444",
                "transaction_amount_alignment_with_established_repeat_spending",
                "in_person_channel_consistent_with_cardholder_routine",
                "device_graph_zero_shared_devices_zero_connected_cards",
            ],
            "contradicting_evidence": [
                "Billing region 444 is an established customer region with 15 prior transactions.",
                "Transaction amount of $77.07 aligns with established repeat spending.",
            ],
            "channel": "in_person",
            "customer_response_status": "unknown",
            "risk_score": 0.61,
        }
        res = rule_r1(ctx_hhg001)
        self.assertFalse(
            res.matched,
            "R1 must NOT match for HHG-001 legitimate case with multiple independent evidence sources merely because 0.05 < 0.70",
        )
        self.assertEqual(res.actions, [])

        # Also verify evaluate_policy does not match R1
        decision = evaluate_policy(ctx_hhg001)
        self.assertNotIn("R1", decision["matched_rules"])
        self.assertNotIn("VERIFY_WITH_CUSTOMER", decision["actions"])

    # ----------------------------------------------------
    # R2: Customer Denies Transaction
    # ----------------------------------------------------
    def test_r2_customer_denies(self):
        """Customer denies transaction -> BLOCK_CARD, CREATE_CASE. Conditionally FILE_REPORT."""
        # Denial with low exposure (<= $1000) and no cluster -> NO FILE_REPORT
        ctx_low = {
            "customer_response_status": "denied",
            "exposure": 250.0,
            "has_shared_device_fraud_cluster": False,
            "has_another_card_fraud": False,
        }
        res_low = rule_r2(ctx_low)
        self.assertTrue(res_low.matched)
        self.assertIn("BLOCK_CARD", res_low.actions)
        self.assertIn("CREATE_CASE", res_low.actions)
        self.assertNotIn("FILE_REPORT", res_low.actions)

        # Denial with high exposure (> $1000) -> FILE_REPORT
        ctx_high_exp = {
            "customer_response_status": "denied",
            "exposure": 1500.0,
            "has_shared_device_fraud_cluster": False,
            "has_another_card_fraud": False,
        }
        res_high_exp = rule_r2(ctx_high_exp)
        self.assertTrue(res_high_exp.matched)
        self.assertIn("BLOCK_CARD", res_high_exp.actions)
        self.assertIn("CREATE_CASE", res_high_exp.actions)
        self.assertIn("FILE_REPORT", res_high_exp.actions)

        # Denial with shared device cluster -> FILE_REPORT
        ctx_shared_dev = {
            "customer_response_status": "denied",
            "exposure": 300.0,
            "has_shared_device_fraud_cluster": True,
            "has_another_card_fraud": False,
        }
        res_shared_dev = rule_r2(ctx_shared_dev)
        self.assertTrue(res_shared_dev.matched)
        self.assertIn("FILE_REPORT", res_shared_dev.actions)

        # Denial with another card's fraud established -> FILE_REPORT
        ctx_other_card = {
            "customer_response_status": "denied",
            "exposure": 120.0,
            "has_shared_device_fraud_cluster": False,
            "has_another_card_fraud": True,
        }
        res_other_card = rule_r2(ctx_other_card)
        self.assertTrue(res_other_card.matched)
        self.assertIn("FILE_REPORT", res_other_card.actions)

    # ----------------------------------------------------
    # R3: Customer Confirms Transaction
    # ----------------------------------------------------
    def test_r3_customer_confirms(self):
        """Customer confirms transaction -> CLOSE_NO_FRAUD. Do not block card."""
        ctx = {
            "customer_response_status": "confirmed",
            "exposure": 77.07,
            "has_historical_fraud": True,  # Precedent fraud should not block
        }
        res = rule_r3(ctx)
        self.assertTrue(res.matched)
        self.assertEqual(res.actions, ["CLOSE_NO_FRAUD"])
        self.assertNotIn("BLOCK_CARD", res.actions)

    # ----------------------------------------------------
    # R4: No Customer Response After 24 Hours
    # ----------------------------------------------------
    def test_r4_no_response_24h(self):
        """No response after 24h -> MONITOR_CARD, DECLINE_TRANSACTION. If exposure > $500, ESCALATE_TO_ANALYST."""
        # 24h elapsed, exposure <= $500
        ctx_low = {
            "customer_response_status": "no_response",
            "hours_since_outreach": 25.0,
            "exposure": 320.0,
        }
        res_low = rule_r4(ctx_low)
        self.assertTrue(res_low.matched)
        self.assertIn("MONITOR_CARD", res_low.actions)
        self.assertIn("DECLINE_TRANSACTION", res_low.actions)
        self.assertNotIn("ESCALATE_TO_ANALYST", res_low.actions)

        # 24h elapsed, exposure > $500 -> ESCALATE_TO_ANALYST
        ctx_high = {
            "customer_response_status": "no_response",
            "hours_since_outreach": 28.0,
            "exposure": 750.0,
        }
        res_high = rule_r4(ctx_high)
        self.assertTrue(res_high.matched)
        self.assertIn("MONITOR_CARD", res_high.actions)
        self.assertIn("DECLINE_TRANSACTION", res_high.actions)
        self.assertIn("ESCALATE_TO_ANALYST", res_high.actions)

    # ----------------------------------------------------
    # R5: Card Testing Pattern
    # ----------------------------------------------------
    def test_r5_card_testing(self):
        """Card testing: 3+ small authorizations within 1 hr followed by larger purchase."""
        # Card testing with <= $100 cleared
        ctx_low_cleared = {
            "has_card_testing_pattern": True,
            "cleared_amount_card_testing": 45.0,
        }
        res_low = rule_r5(ctx_low_cleared)
        self.assertTrue(res_low.matched)
        self.assertIn("DECLINE_TRANSACTION", res_low.actions)
        self.assertIn("STEP_UP_AUTH", res_low.actions)
        self.assertNotIn("BLOCK_CARD", res_low.actions)

        # Card testing with > $100 cleared -> BLOCK_CARD
        ctx_high_cleared = {
            "has_card_testing_pattern": True,
            "cleared_amount_card_testing": 149.50,
        }
        res_high = rule_r5(ctx_high_cleared)
        self.assertTrue(res_high.matched)
        self.assertIn("DECLINE_TRANSACTION", res_high.actions)
        self.assertIn("STEP_UP_AUTH", res_high.actions)
        self.assertIn("BLOCK_CARD", res_high.actions)

    # ----------------------------------------------------
    # R6: Shared Origin Fraud Cluster
    # ----------------------------------------------------
    def test_r6_shared_origin(self):
        """Shared origin fraud cluster across multiple cards."""
        ctx_cluster = {
            "has_shared_device_fraud_cluster": True,
            "has_shared_region_fraud_cluster": False,
        }
        res = rule_r6(ctx_cluster)
        self.assertTrue(res.matched)
        self.assertIn("CREATE_CASE", res.actions)
        self.assertIn("FILE_REPORT", res.actions)
        self.assertIn("MONITOR_CONNECTED_CARDS", res.actions)

    # ----------------------------------------------------
    # R7: Disputed Legitimate Recurring Pattern
    # ----------------------------------------------------
    def test_r7_disputed_legitimate(self):
        """Disputed but legitimate recurring pattern -> CREATE_CASE, VERIFY_WITH_CUSTOMER, WARN_CUSTOMER. No block."""
        ctx = {
            "is_disputed_legitimate_recurring": True,
        }
        res = rule_r7(ctx)
        self.assertTrue(res.matched)
        self.assertIn("CREATE_CASE", res.actions)
        self.assertIn("VERIFY_WITH_CUSTOMER", res.actions)
        self.assertIn("WARN_CUSTOMER", res.actions)
        self.assertNotIn("BLOCK_CARD", res.actions)

    # ----------------------------------------------------
    # R8: Uncertain High Exposure or Conflicting Evidence
    # ----------------------------------------------------
    def test_r8_uncertain_high_exposure(self):
        """Uncertain AND (exposure > $500 OR conflicting evidence requiring analyst)."""
        # Uncertain with exposure $77.07 (does not escalate)
        ctx_low = {
            "verdict": "uncertain",
            "exposure": 77.07,
            "conflicting_evidence_requiring_analyst": False,
        }
        res_low = rule_r8(ctx_low)
        self.assertFalse(res_low.matched)

        # Uncertain with exposure $850 (> $500) -> escalates
        ctx_high = {
            "verdict": "uncertain",
            "exposure": 850.0,
            "conflicting_evidence_requiring_analyst": False,
        }
        res_high = rule_r8(ctx_high)
        self.assertTrue(res_high.matched)
        self.assertIn("ESCALATE_TO_ANALYST", res_high.actions)

        # Uncertain with exposure $200 but conflicting evidence requiring analyst review -> escalates
        ctx_conflict = {
            "verdict": "uncertain",
            "exposure": 200.0,
            "conflicting_evidence_requiring_analyst": True,
        }
        res_conflict = rule_r8(ctx_conflict)
        self.assertTrue(res_conflict.matched)
        self.assertIn("ESCALATE_TO_ANALYST", res_conflict.actions)

    # ----------------------------------------------------
    # R9: Undocumented Coordinated Abuse
    # ----------------------------------------------------
    def test_r9_undocumented_coordinated_abuse(self):
        """Undocumented coordinated/repeated abuse across customers."""
        ctx = {
            "has_undocumented_abuse": True,
        }
        res = rule_r9(ctx)
        self.assertTrue(res.matched)
        self.assertIn("CREATE_CASE", res.actions)
        self.assertIn("FILE_REPORT", res.actions)
        self.assertIn("ESCALATE_TO_ANALYST", res.actions)

    # ----------------------------------------------------
    # R10: Block All Cards Guard
    # ----------------------------------------------------
    def test_r10_block_all_cards_guard(self):
        """NEVER BLOCK_ALL_CARDS unless 2+ cards confirmed fraud or credentials confirmed compromised."""
        # 1 card compromised, creds not confirmed compromised -> block all cards disallowed
        ctx_one_card = {
            "confirmed_compromised_cards_count": 1,
            "credentials_confirmed_compromised": False,
        }
        res_one = rule_r10(ctx_one_card)
        self.assertFalse(res_one.metadata.get("allow_block_all_cards"))

        # 2 cards compromised -> allowed
        ctx_two_cards = {
            "confirmed_compromised_cards_count": 2,
            "credentials_confirmed_compromised": False,
        }
        res_two = rule_r10(ctx_two_cards)
        self.assertTrue(res_two.metadata.get("allow_block_all_cards"))

        # Credentials confirmed compromised -> allowed
        ctx_creds = {
            "confirmed_compromised_cards_count": 1,
            "credentials_confirmed_compromised": True,
        }
        res_creds = rule_r10(ctx_creds)
        self.assertTrue(res_creds.metadata.get("allow_block_all_cards"))


class TestGlobalRulesAndThresholds(unittest.TestCase):
    """Test suite verifying mandatory CREATE_CASE and FILE_REPORT requirements."""

    # ----------------------------------------------------
    # CREATE_CASE Rule
    # ----------------------------------------------------
    def test_create_case_probability_threshold(self):
        """CREATE_CASE whenever fraud probability >= 0.30."""
        # Probability 0.35 -> CREATE_CASE
        ctx_match = {"fraud_probability": 0.35, "evidence_requests": [], "customer_response_status": "unknown"}
        self.assertTrue(rule_create_case(ctx_match).matched)

        # Probability 0.20 -> No CREATE_CASE
        ctx_no_match = {"fraud_probability": 0.20, "evidence_requests": [], "customer_response_status": "unknown"}
        self.assertFalse(rule_create_case(ctx_no_match).matched)

    def test_create_case_evidence_request(self):
        """CREATE_CASE whenever external evidence is requested."""
        ctx = {
            "fraud_probability": 0.15,
            "evidence_requests": [{"request_type": "customer_confirmation", "transaction_id": "3514030"}],
            "customer_response_status": "unknown",
        }
        res = rule_create_case(ctx)
        self.assertTrue(res.matched)
        self.assertIn("CREATE_CASE", res.actions)

    def test_create_case_customer_dispute(self):
        """CREATE_CASE whenever customer disputes transaction."""
        ctx = {
            "fraud_probability": 0.10,
            "evidence_requests": [],
            "customer_response_status": "denied",
        }
        res = rule_create_case(ctx)
        self.assertTrue(res.matched)
        self.assertIn("CREATE_CASE", res.actions)

    # ----------------------------------------------------
    # FILE_REPORT Rule
    # ----------------------------------------------------
    def test_file_report_exposure_threshold(self):
        """FILE_REPORT when fraud is confirmed/suspected AND exposure > $1,000."""
        ctx_match = {
            "verdict": "suspected_fraud",
            "fraud_probability": 0.85,
            "exposure": 1250.0,
            "has_shared_device_fraud_cluster": False,
        }
        self.assertTrue(rule_file_report(ctx_match).matched)

        # Exposure <= 1000 without other triggers -> NO FILE_REPORT
        ctx_no_match = {
            "verdict": "suspected_fraud",
            "fraud_probability": 0.85,
            "exposure": 450.0,
            "has_shared_device_fraud_cluster": False,
        }
        self.assertFalse(rule_file_report(ctx_no_match).matched)

    def test_file_report_shared_device(self):
        """FILE_REPORT when fraud confirmed/suspected AND shared device fraud cluster."""
        ctx = {
            "verdict": "confirmed_fraud",
            "fraud_probability": 0.95,
            "exposure": 150.0,
            "has_shared_device_fraud_cluster": True,
        }
        res = rule_file_report(ctx)
        self.assertTrue(res.matched)
        self.assertIn("FILE_REPORT", res.actions)

    def test_file_report_shared_region_cluster(self):
        """FILE_REPORT when fraud confirmed/suspected AND shared region fraud cluster."""
        ctx = {
            "verdict": "confirmed_fraud",
            "fraud_probability": 0.90,
            "exposure": 80.0,
            "has_shared_region_fraud_cluster": True,
        }
        res = rule_file_report(ctx)
        self.assertTrue(res.matched)
        self.assertIn("FILE_REPORT", res.actions)

    def test_file_report_other_customer_fraud(self):
        """FILE_REPORT when fraud confirmed/suspected AND another customer's fraud."""
        ctx = {
            "verdict": "suspected_fraud",
            "fraud_probability": 0.75,
            "exposure": 220.0,
            "has_other_customer_fraud": True,
        }
        res = rule_file_report(ctx)
        self.assertTrue(res.matched)
        self.assertIn("FILE_REPORT", res.actions)


class TestCustomerResponseStatesAndGuards(unittest.TestCase):
    """Test suite verifying unknown customer response does not assume confirmation or denial."""

    def test_unknown_customer_response_does_not_trigger_r2(self):
        """Unknown customer response must NOT trigger R2 (no denial assumption)."""
        ctx = {
            "customer_response_status": "unknown",
            "exposure": 77.07,
            "fraud_probability": 0.42,
        }
        res = rule_r2(ctx)
        self.assertFalse(res.matched)

    def test_unknown_customer_response_does_not_trigger_r3(self):
        """Unknown customer response must NOT trigger R3 (no confirmation assumption)."""
        ctx = {
            "customer_response_status": "unknown",
            "exposure": 77.07,
            "fraud_probability": 0.42,
        }
        res = rule_r3(ctx)
        self.assertFalse(res.matched)

    def test_unknown_customer_response_does_not_trigger_r4(self):
        """Unknown customer response must NOT trigger R4 unless 24 hours elapsed."""
        ctx = {
            "customer_response_status": "unknown",
            "hours_since_outreach": 1.5,
            "exposure": 77.07,
        }
        res = rule_r4(ctx)
        self.assertFalse(res.matched)

    def test_common_gmail_domain_not_treated_as_fraud_cluster(self):
        """Generic email domain (gmail.com) alone must NOT trigger R6 or FILE_REPORT."""
        decision = evaluate_policy({
            "verdict": "uncertain",
            "fraud_probability": 0.42,
            "exposure": 77.07,
            "shared_email_domain": "gmail.com",
            "has_shared_device_fraud_cluster": False,
            "has_shared_region_fraud_cluster": False,
            "has_other_customer_fraud": False,
        })
        self.assertNotIn("R6", decision["matched_rules"])
        self.assertNotIn("FILE_REPORT", decision["actions"])

    def test_common_region_alone_not_treated_as_fraud_cluster(self):
        """Common anonymized billing region alone must NOT trigger R6 or FILE_REPORT."""
        decision = evaluate_policy({
            "verdict": "uncertain",
            "fraud_probability": 0.42,
            "exposure": 77.07,
            "billing_region": "444",
            "has_shared_device_fraud_cluster": False,
            "has_shared_region_fraud_cluster": False,
            "has_other_customer_fraud": False,
        })
        self.assertNotIn("R6", decision["matched_rules"])
        self.assertNotIn("FILE_REPORT", decision["actions"])


class TestPolicyConflictResolution(unittest.TestCase):
    """Test suite verifying conflicting policy conditions and precedence rules."""

    def test_uncertain_high_exposure_unknown_response(self):
        """
        Uncertain + exposure > $500 + response unknown
        Escalates according to R8, without pretending customer denied.
        """
        decision = evaluate_policy({
            "verdict": "uncertain",
            "fraud_probability": 0.45,
            "exposure": 850.0,
            "customer_response_status": "unknown",
            "evidence_requests": [{"request_type": "customer_confirmation", "transaction_id": "999"}],
        })
        self.assertIn("ESCALATE_TO_ANALYST", decision["actions"])
        self.assertIn("CREATE_CASE", decision["actions"])
        self.assertNotIn("BLOCK_CARD", decision["actions"])
        self.assertEqual(decision["customer_response_status"], "unknown")

    def test_customer_confirmed_with_historical_fraud(self):
        """
        Customer confirmed + historical fraud
        Customer confirmation enforces CLOSE_NO_FRAUD and does not trigger R2 or card block.
        """
        decision = evaluate_policy({
            "verdict": "legitimate",
            "fraud_probability": 0.10,
            "exposure": 77.07,
            "customer_response_status": "confirmed",
            "has_another_card_fraud": True,
        })
        self.assertIn("CLOSE_NO_FRAUD", decision["actions"])
        self.assertNotIn("BLOCK_CARD", decision["actions"])
        self.assertNotIn("R2", decision["matched_rules"])

    def test_customer_denied_high_exposure(self):
        """
        Customer denied + exposure > $1000
        Must produce BLOCK_CARD, CREATE_CASE, and FILE_REPORT.
        """
        decision = evaluate_policy({
            "verdict": "confirmed_fraud",
            "fraud_probability": 0.90,
            "exposure": 2400.0,
            "customer_response_status": "denied",
        })
        self.assertIn("BLOCK_CARD", decision["actions"])
        self.assertIn("CREATE_CASE", decision["actions"])
        self.assertIn("FILE_REPORT", decision["actions"])
        self.assertEqual(decision["primary_action"], "BLOCK_CARD")

    def test_customer_denied_low_exposure_no_cluster(self):
        """
        Customer denied + exposure <= $1000 + no shared cluster
        Must produce BLOCK_CARD and CREATE_CASE, but NOT FILE_REPORT.
        """
        decision = evaluate_policy({
            "verdict": "suspected_fraud",
            "fraud_probability": 0.80,
            "exposure": 350.0,
            "customer_response_status": "denied",
            "has_shared_device_fraud_cluster": False,
            "has_another_card_fraud": False,
        })
        self.assertIn("BLOCK_CARD", decision["actions"])
        self.assertIn("CREATE_CASE", decision["actions"])
        self.assertNotIn("FILE_REPORT", decision["actions"])


if __name__ == "__main__":
    unittest.main()
