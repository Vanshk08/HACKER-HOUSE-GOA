"""
End-to-end integration test for case HHG-001 on the real challenge datasets.
Exercises StateGraph orchestration:
  Case Input -> Investigator -> ToolExecutor (Real Data) -> ... -> Assessment -> END
"""

import os
import sys
import unittest

# Ensure fraud-agent is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import AIMessage, ToolMessage
from agent.state import create_initial_state
from agent.orchestrator import build_investigation_graph, should_continue
from agent.assessment import AssessmentSchema
from tools.hhgoa_data import transaction, customer_history, customer_regions, similar_closed_cases


class DeterministicHHG001InvestigatorLLM:
    """
    Deterministic LLM simulating the Investigator's multi-cycle reasoning
    while allowing the Investigator to decide which tools to request.
    """

    def __init__(self):
        self.call_count = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.call_count += 1

        if self.call_count == 1:
            # Cycle 1: First examine the flagged transaction 3514030
            return AIMessage(
                content="Investigating trigger transaction 3514030 to inspect amount, channel, and region.",
                tool_calls=[{
                    "name": "get_transaction",
                    "args": {"transaction_id": "3514030"},
                    "id": "call_tx_3514030",
                }]
            )

        elif self.call_count == 2:
            # Cycle 2: After seeing flagged txn is in-person in region 444 with amount $77.07,
            # query customer history and regional activity to see if 444 is normal behavior
            return AIMessage(
                content="Transaction is in-person in region 444. Checking customer history and region activity for 444.",
                tool_calls=[
                    {
                        "name": "get_customer_regions",
                        "args": {"customer_id": "C12382"},
                        "id": "call_cust_regions",
                    },
                    {
                        "name": "get_card_history",
                        "args": {"card_id": "C12382-K1"},
                        "id": "call_card_hist",
                    },
                ]
            )

        elif self.call_count == 3:
            # Cycle 3: Check precedent closed cases to understand historical fraud patterns
            return AIMessage(
                content="Checking historical closed cases for C12382 to examine precedent patterns.",
                tool_calls=[{
                    "name": "get_similar_closed_cases",
                    "args": {"customer_id": "C12382"},
                    "id": "call_closed_cases",
                }]
            )

        elif self.call_count == 4:
            # Cycle 4: Final synthesis - no more tools needed
            return AIMessage(
                content="""INVESTIGATION SYNTHESIS FOR HHG-001:
1. FLAGGED TRANSACTION:
   - Transaction 3514030: Amount $77.07, channel 'in_person' (ProductCD=W), billing region 444, risk_score 0.61.
2. CUSTOMER HISTORY & REGIONAL ACTIVITY:
   - Customer C12382 has 422 total transactions across multiple regions.
   - Billing region 444 is NOT an unseen region: customer has 15 transactions in region 444 totaling $1,049.26 spanning Sept–Dec 2016.
   - Transaction amount $77.07 matches the customer's typical spending in this region ($76.96 - $77.05).
3. HISTORICAL CLOSED CASES (CONTEXT):
   - Card C12382-K1 had 4 prior confirmed fraud cases in July-Sept 2016 (CC-1066, CC-1673, CC-2964, CC-3587) involving out-of-region card cloning.
   - However, closed cases are historical context, not proof that transaction 3514030 is fraudulent.
4. UNCERTAINTY & LEGITIMATE EXPLANATION:
   - Customer has established physical presence in region 444 with identical transaction amounts.
   - Without direct customer confirmation, authorization cannot be conclusively determined.
Investigation concluded.""",
                tool_calls=[]
            )

        raise RuntimeError(f"Unexpected extra investigator call {self.call_count}")


class DeterministicHHG001AssessmentLLM:
    """
    Deterministic LLM simulating the Assessment Agent evaluating gathered evidence.
    Produces structured Assessment output adhering to the 9-field schema.
    """

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return AssessmentSchema(
            verdict="uncertain",
            fraud_probability=0.48,  # Evidence-based, distinct from trigger risk_score 0.61
            fraud_type=None,
            exposure=77.07,
            affected_txn_ids=["3514030"],
            supporting_evidence=[
                "Card C12382-K1 has historical precedent of confirmed card cloning and out-of-region fraud (cases CC-1066, CC-2964, CC-3587).",
                "Transaction was flagged with elevated model risk score of 0.61.",
            ],
            contradicting_evidence=[
                "Billing region 444 is an established customer region with 15 prior transactions totaling $1,049.26 between Sept-Dec 2016.",
                "Transaction amount of $77.07 perfectly aligns with established repeat amounts ($76.96 - $77.05) in region 444.",
                "Transaction was conducted in-person (ProductCD=W), consistent with customer's standard channel.",
            ],
            reasoning="Evidence is balanced between legitimate repeat spending and potential card cloning. Billing region 444 is well-established in the customer's historical profile, contradicting a simple out-of-region fraud hypothesis. However, previous confirmed fraud on this card indicates historical compromise. Decisive evidence regarding authorization is absent, necessitating an uncertain verdict.",
            confidence=0.55,
        )


class TestHHG001EndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.case_row = {
            "case_id": "HHG-001",
            "customer_id": "C12382",
            "card_id": "C12382-K1",
            "flagged_txn_id": "3514030",
        }

    def test_hhg001_real_data_access(self):
        """Verify HHGOA_IEEE returns factual records for HHG-001."""
        tx = transaction("3514030")
        self.assertEqual(tx["amount"], 77.07)
        self.assertEqual(tx["customer_id"], "C12382")
        self.assertEqual(tx["backend_status"], "hhgoa_ieee")
        self.assertGreater(customer_history("C12382")["total_transactions"], 0)
        self.assertIn("444.0", customer_regions("C12382")["region_codes"])
        self.assertGreater(similar_closed_cases(customer_id="C12382")["total_matches"], 0)

    def test_hhg001_graph_e2e_execution(self):
        """Exercise full LangGraph StateGraph on HHG-001 using real data tools."""
        inv_llm = DeterministicHHG001InvestigatorLLM()
        ass_llm = DeterministicHHG001AssessmentLLM()

        graph = build_investigation_graph(inv_llm, assessment_llm=ass_llm)

        # Initialize real case state from case_pack
        init_state = create_initial_state(
            case_id=self.case_row["case_id"],
            customer_id=self.case_row["customer_id"],
            card_id=self.case_row["card_id"],
            flagged_txn_id=str(self.case_row["flagged_txn_id"]),
        )

        final_state = graph.invoke(init_state)

        # Part 10: State Verification
        self.assertEqual(final_state["case_id"], "HHG-001")
        self.assertEqual(final_state["customer_id"], "C12382")
        self.assertEqual(final_state["card_id"], "C12382-K1")
        self.assertEqual(final_state["flagged_txn_id"], "3514030")

        # Verify messages history
        messages = final_state.get("messages", [])
        self.assertGreater(len(messages), 4)
        msg_types = [type(m).__name__ for m in messages]
        self.assertIn("SystemMessage", msg_types)
        self.assertIn("HumanMessage", msg_types)
        self.assertIn("AIMessage", msg_types)
        self.assertIn("ToolMessage", msg_types)

        # Verify real evidence objects
        evidence = final_state.get("evidence", [])
        self.assertGreaterEqual(len(evidence), 4)

        # Verify evidence provenance
        evidence_sources = [e["source"] for e in evidence]
        self.assertIn("get_transaction", evidence_sources)
        self.assertIn("get_customer_regions", evidence_sources)
        self.assertIn("get_card_history", evidence_sources)
        self.assertIn("get_similar_closed_cases", evidence_sources)

        for e in evidence:
            self.assertEqual(e["type"], "tool_result")
            self.assertEqual(e["confidence"], 1.0)
            self.assertIn("data", e)

        # Part 9: Verify real data is used (not synthetic)
        tx_ev = next(e for e in evidence if e["source"] == "get_transaction")
        self.assertEqual(tx_ev["data"]["result"]["transaction_id"], "3514030")
        self.assertEqual(tx_ev["data"]["result"]["customer_id"], "C12382")
        self.assertEqual(tx_ev["data"]["result"]["amount"], 77.07)

        # Verify tools_used
        tools_used = final_state.get("tools_used", [])
        self.assertIn("get_transaction", tools_used)
        self.assertIn("get_customer_regions", tools_used)
        self.assertIn("get_card_history", tools_used)
        self.assertIn("get_similar_closed_cases", tools_used)

        # Part 11: Assessment Verification
        ass = final_state.get("assessment")
        self.assertIsNotNone(ass, "state['assessment'] was not populated")

        # 9 structured fields check
        required_fields = [
            "verdict",
            "fraud_probability",
            "fraud_type",
            "exposure",
            "affected_txn_ids",
            "supporting_evidence",
            "contradicting_evidence",
            "reasoning",
            "confidence",
        ]
        for f in required_fields:
            self.assertIn(f, ass, f"Assessment missing field: {f}")

        # Verdict check
        self.assertIn(ass["verdict"], ["confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"])
        self.assertEqual(ass["verdict"], "uncertain")

        # Probability & confidence bounds
        self.assertGreaterEqual(ass["fraud_probability"], 0.0)
        self.assertLessEqual(ass["fraud_probability"], 1.0)
        # Verify fraud_probability is independently assessed, not copied from risk_score (0.61)
        self.assertNotEqual(ass["fraud_probability"], 0.61)

        self.assertGreaterEqual(ass["confidence"], 0.0)
        self.assertLessEqual(ass["confidence"], 1.0)

        # Affected transactions and exposure
        self.assertEqual(ass["affected_txn_ids"], ["3514030"])
        self.assertAlmostEqual(ass["exposure"], 77.07, places=2)

        # Supporting and contradicting evidence
        self.assertGreaterEqual(len(ass["supporting_evidence"]), 1)
        self.assertGreaterEqual(len(ass["contradicting_evidence"]), 1)
        self.assertIsInstance(ass["reasoning"], str)
        self.assertGreater(len(ass["reasoning"]), 20)

        print("\n=== HHG-001 End-to-End Test Execution Summary ===")
        print(f"Case ID: {final_state['case_id']}")
        print(f"Customer ID: {final_state['customer_id']}")
        print(f"Card ID: {final_state['card_id']}")
        print(f"Flagged Txn: {final_state['flagged_txn_id']}")
        print(f"Iterations: {final_state.get('iteration_count')}")
        print(f"Total Tools Used: {len(tools_used)} -> {tools_used}")
        print(f"Total Evidence Items: {len(evidence)}")
        print(f"Final Verdict: {ass['verdict']}")
        print(f"Fraud Probability: {ass['fraud_probability']} (Independent, vs Trigger Risk Score 0.61)")
        print(f"Confidence: {ass['confidence']}")
        print(f"Exposure: ${ass['exposure']}")
        print(f"Affected Txns: {ass['affected_txn_ids']}")
        print(f"Reasoning: {ass['reasoning']}")


if __name__ == "__main__":
    unittest.main()
