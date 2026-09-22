"""
End-to-end integration test for Case HHG-001 through the full pipeline:
Case Input -> Investigator -> ToolExecutor (Real TigerGraph Data) -> Assessment -> Policy Engine -> END

Verifies:
1. Investigator runs normally with real challenge data.
2. Assessment runs normally.
3. Policy Engine runs after Assessment and has NO investigation tools.
4. Policy decision is present in state["policy_decision"] with valid actions.
5. R1 and GLOBAL_CREATE_CASE match deterministically for HHG-001.
6. Unknown customer response is strictly preserved as 'unknown' (not assumed denial or confirmation).
7. No BLOCK_CARD or FILE_REPORT is produced for the $77.07 transaction.
8. StateGraph terminates cleanly at END.
"""

import os
import sys
import unittest

# Ensure fraud-agent is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import AIMessage
from agent.state import create_initial_state
from agent.orchestrator import build_investigation_graph
from agent.assessment import AssessmentSchema
from agent.policy import PolicyAgent
from schemas.decision import VALID_ACTIONS


class HHG001PolicyInvestigatorLLM:
    """
    Autonomous deterministic investigator that queries Real TigerGraph Data tools
    based on missing evidence.
    """

    def __init__(self):
        self.call_count = 0
        self.tool_sequence = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.call_count += 1

        executed_tools = set()
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    executed_tools.add(tc["name"])

        # Cycle 1: Flagged transaction
        if "get_transaction" not in executed_tools:
            self.tool_sequence.append("get_transaction")
            return AIMessage(
                content="Investigating flagged transaction 3514030.",
                tool_calls=[{
                    "name": "get_transaction",
                    "args": {"transaction_id": "3514030"},
                    "id": "call_tx_3514030",
                }]
            )

        # Cycle 2: Customer history and regional spending
        missing_cust = [t for t in ["get_customer_history", "get_customer_regions"] if t not in executed_tools]
        if missing_cust:
            self.tool_sequence.extend(missing_cust)
            return AIMessage(
                content="Checking customer history and billing regions.",
                tool_calls=[
                    {"name": "get_customer_history", "args": {"customer_id": "C12382"}, "id": "call_cust_hist"},
                    {"name": "get_customer_regions", "args": {"customer_id": "C12382"}, "id": "call_cust_reg"},
                ]
            )

        # Cycle 3: Card history and closed cases precedent
        missing_card = [t for t in ["get_card_history", "get_similar_closed_cases"] if t not in executed_tools]
        if missing_card:
            self.tool_sequence.extend(missing_card)
            return AIMessage(
                content="Checking card history and similar closed cases.",
                tool_calls=[
                    {"name": "get_card_history", "args": {"card_id": "C12382-K1"}, "id": "call_card_hist"},
                    {"name": "get_similar_closed_cases", "args": {"customer_id": "C12382"}, "id": "call_closed_cases"},
                ]
            )

        # Cycle 4: Graph connections and shared origins
        missing_graph = [t for t in ["get_device_connections", "find_shared_origins"] if t not in executed_tools]
        if missing_graph:
            self.tool_sequence.extend(missing_graph)
            return AIMessage(
                content="Checking device connections and shared origins.",
                tool_calls=[
                    {"name": "get_device_connections", "args": {"customer_id": "C12382"}, "id": "call_dev_conn"},
                    {"name": "find_shared_origins", "args": {"customer_id": "C12382"}, "id": "call_shared_origins"},
                ]
            )

        # Cycle 5: Register external customer validation request
        if "request_customer_validation" not in executed_tools:
            self.tool_sequence.append("request_customer_validation")
            return AIMessage(
                content="Registering customer validation request for unknown cardholder authorization.",
                tool_calls=[{
                    "name": "request_customer_validation",
                    "args": {
                        "transaction_id": "3514030",
                        "question": "Did you authorize in-person transaction 3514030 for $77.07 in region 444?"
                    },
                    "id": "call_req_val",
                }]
            )

        # Cycle 6: Final synthesis - stop tool calls
        return AIMessage(
            content="Investigation complete. Flagged transaction is $77.07 in established region 444 (15 prior visits). Precedent card compromise exists, but authorization is unknown. Customer confirmation is pending.",
            tool_calls=[]
        )


class HHG001PolicyAssessmentLLM:
    """Assessment LLM producing structured Assessment without hardcoded policy decisions."""

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return AssessmentSchema(
            verdict="uncertain",
            fraud_probability=0.42,
            fraud_type=None,
            exposure=77.07,
            affected_txn_ids=["3514030"],
            supporting_evidence=[
                "Card C12382-K1 has historical precedent of confirmed card cloning (cases CC-1066, CC-2964, CC-3587).",
                "Transaction flagged with elevated model risk score of 0.61.",
            ],
            contradicting_evidence=[
                "Billing region 444 is an established customer region with 15 prior transactions totaling $1,049.26 spanning Sept-Dec 2016.",
                "Transaction amount ($77.07) perfectly aligns with repeat spending ($76.96-$77.05) in region 444.",
                "Transaction was in-person (ProductCD=W), consistent with cardholder regular channel.",
                "Zero shared devices and zero connected cards found in graph exploration.",
            ],
            reasoning="Evidence is balanced between legitimate repeat spending and historical card cloning precedent. Authorization is unknown pending customer response.",
            confidence=0.62,
        )


class TestHHG001PolicyEndToEnd(unittest.TestCase):
    """End-to-end integration test verifying Policy Engine on HHG-001."""

    @classmethod
    def setUpClass(cls):
        cls.case_row = {"case_id": "HHG-001", "customer_id": "C12382", "card_id": "C12382-K1", "flagged_txn_id": "3514030"}

    def test_hhg001_full_pipeline_to_policy_decision(self):
        """
        Execute full StateGraph:
        Case -> Investigator -> ToolExecutor -> Assessment -> Policy -> END
        """
        inv_llm = HHG001PolicyInvestigatorLLM()
        ass_llm = HHG001PolicyAssessmentLLM()
        policy_agent = PolicyAgent()

        # 4. Verify Policy Agent has no investigation tools
        self.assertFalse(hasattr(policy_agent, "tools"), "PolicyAgent must not have investigation tools")
        self.assertIsNone(getattr(policy_agent, "tools", None))

        graph = build_investigation_graph(
            inv_llm,
            assessment_llm=ass_llm,
            policy=policy_agent,
        )

        init_state = create_initial_state(
            case_id=self.case_row["case_id"],
            customer_id=self.case_row["customer_id"],
            card_id=self.case_row["card_id"],
            flagged_txn_id=str(self.case_row["flagged_txn_id"]),
        )

        final_state = graph.invoke(init_state)

        # 1. State preservation
        self.assertEqual(final_state["case_id"], "HHG-001")
        self.assertEqual(final_state["customer_id"], "C12382")
        self.assertEqual(final_state["card_id"], "C12382-K1")
        self.assertEqual(final_state["flagged_txn_id"], "3514030")

        # 2. Assessment verification
        ass = final_state.get("assessment")
        self.assertIsNotNone(ass)
        self.assertEqual(ass["verdict"], "uncertain")
        self.assertEqual(ass["affected_txn_ids"], ["3514030"])
        self.assertAlmostEqual(ass["exposure"], 77.07, places=2)

        # 3. Policy decision presence
        policy_dec = final_state.get("policy_decision")
        self.assertIsNotNone(policy_dec, "state['policy_decision'] was not populated")

        # 6. Matched rules
        matched_rules = policy_dec.get("matched_rules", [])
        self.assertIn("R1", matched_rules, "Expected R1 to match for weak single signal / uncertain")
        self.assertIn("GLOBAL_CREATE_CASE", matched_rules, "Expected GLOBAL_CREATE_CASE to match (prob >= 0.30, requests exist)")

        # 7. Valid actions
        actions = policy_dec.get("actions", [])
        for act in actions:
            self.assertIn(act, VALID_ACTIONS, f"Invalid policy action: {act}")

        self.assertIn("CREATE_CASE", actions)
        self.assertIn("VERIFY_WITH_CUSTOMER", actions)

        # 8 & 9. Exposure and affected transactions
        self.assertEqual(policy_dec.get("affected_txn_ids"), ["3514030"])
        self.assertAlmostEqual(policy_dec.get("exposure"), 77.07, places=2)

        # 10. No BLOCK_CARD produced solely because of historical fraud
        self.assertNotIn("BLOCK_CARD", actions, "Must NOT produce BLOCK_CARD for HHG-001")

        # 11. No FILE_REPORT produced for current $77.07 exposure without required cluster
        self.assertNotIn("FILE_REPORT", actions, "Must NOT produce FILE_REPORT for HHG-001 ($77.07 exposure)")

        # 12. Unknown customer response is preserved, not treated as denial
        self.assertEqual(policy_dec.get("customer_response_status"), "unknown")
        self.assertNotIn("R2", matched_rules, "Must NOT trigger R2 without customer denial")
        self.assertNotIn("R3", matched_rules, "Must NOT trigger R3 without customer confirmation")
        self.assertNotIn("R4", matched_rules, "Must NOT trigger R4 without 24h elapsed")

        # 13. Requires customer response is True
        self.assertTrue(policy_dec.get("requires_customer_response"))

        # Primary action is valid
        self.assertIn(policy_dec.get("primary_action"), ["VERIFY_WITH_CUSTOMER", "CREATE_CASE"])

        print("\n" + "=" * 70)
        print("HHG-001 END-TO-END POLICY TEST EXECUTION SUMMARY")
        print("=" * 70)
        print(f"CASE: {final_state['case_id']}")
        print(f"ASSESSMENT VERDICT: {ass['verdict']}")
        print(f"FRAUD PROBABILITY: {ass['fraud_probability']}")
        print(f"EXPOSURE: ${policy_dec['exposure']:.2f}")
        print(f"MATCHED RULES: {policy_dec['matched_rules']}")
        print(f"FINAL ACTIONS: {policy_dec['actions']}")
        print(f"PRIMARY ACTION: {policy_dec['primary_action']}")
        print(f"CUSTOMER RESPONSE STATUS: {policy_dec['customer_response_status']}")
        print(f"REQUIRES CUSTOMER RESPONSE: {policy_dec['requires_customer_response']}")
        print(f"GRAPH EXECUTION PATH: START -> investigator -> tool_executor -> assessment -> policy -> END")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    unittest.main()
