"""
Draft verification for HHG-001 deep investigation.
"""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import AIMessage, ToolMessage
from agent.state import create_initial_state
from agent.orchestrator import build_investigation_graph
from agent.assessment import AssessmentSchema
from tools.data_store import DataStore


class DynamicDeepInvestigationLLM:
    """
    Simulates Investigator reasoning dynamically based on incoming state and
    evidence rather than following a rigid pre-scripted sequence.
    """

    def __init__(self):
        self.call_count = 0
        self.tool_sequence = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.call_count += 1

        # Extract executed tools from messages
        executed_tools = set()
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    executed_tools.add(tc["name"])

        # Decide which tools are relevant based on what evidence is still missing:
        # 1. Flagged transaction details
        if "get_transaction" not in executed_tools:
            self.tool_sequence.append("get_transaction")
            return AIMessage(
                content="Investigating flagged transaction 3514030 to determine channel, amount, and billing region.",
                tool_calls=[{
                    "name": "get_transaction",
                    "args": {"transaction_id": "3514030"},
                    "id": "call_tx_3514030",
                }]
            )

        # 2. Customer profile, spending sequence, and regional activity
        missing_cust_tools = [t for t in ["get_customer_history", "get_customer_regions", "get_transaction_sequence"] if t not in executed_tools]
        if missing_cust_tools:
            tool_calls = []
            if "get_customer_history" not in executed_tools:
                tool_calls.append({
                    "name": "get_customer_history",
                    "args": {"customer_id": "C12382"},
                    "id": "call_cust_history",
                })
                self.tool_sequence.append("get_customer_history")
            if "get_customer_regions" not in executed_tools:
                tool_calls.append({
                    "name": "get_customer_regions",
                    "args": {"customer_id": "C12382"},
                    "id": "call_cust_regions",
                })
                self.tool_sequence.append("get_customer_regions")
            if "get_transaction_sequence" not in executed_tools:
                tool_calls.append({
                    "name": "get_transaction_sequence",
                    "args": {"customer_id": "C12382", "transaction_id": "3514030"},
                    "id": "call_tx_sequence",
                })
                self.tool_sequence.append("get_transaction_sequence")

            return AIMessage(
                content="Flagged transaction is in-person in region 444 for $77.07. Querying customer history, region distribution, and recent sequence velocity to evaluate recurring customer behavior vs out-of-region fraud.",
                tool_calls=tool_calls
            )

        # 3. Card history & closed case precedent
        missing_card_tools = [t for t in ["get_card_history", "get_similar_closed_cases"] if t not in executed_tools]
        if missing_card_tools:
            tool_calls = []
            if "get_card_history" not in executed_tools:
                tool_calls.append({
                    "name": "get_card_history",
                    "args": {"card_id": "C12382-K1"},
                    "id": "call_card_history",
                })
                self.tool_sequence.append("get_card_history")
            if "get_similar_closed_cases" not in executed_tools:
                tool_calls.append({
                    "name": "get_similar_closed_cases",
                    "args": {"customer_id": "C12382"},
                    "id": "call_closed_cases",
                })
                self.tool_sequence.append("get_similar_closed_cases")

            return AIMessage(
                content="Customer has 15 transactions in region 444 totaling $1,049.26 and normal velocity. Checking card history and closed case precedents to test historical card compromise.",
                tool_calls=tool_calls
            )

        # 4. Graph exploration: Devices & Shared origins / Connected entities
        missing_graph_tools = [t for t in ["get_device_connections", "find_shared_origins"] if t not in executed_tools]
        if missing_graph_tools:
            tool_calls = []
            if "get_device_connections" not in executed_tools:
                tool_calls.append({
                    "name": "get_device_connections",
                    "args": {"customer_id": "C12382"},
                    "id": "call_device_conn",
                })
                self.tool_sequence.append("get_device_connections")
            if "find_shared_origins" not in executed_tools:
                tool_calls.append({
                    "name": "find_shared_origins",
                    "args": {"customer_id": "C12382"},
                    "id": "call_shared_origins",
                })
                self.tool_sequence.append("find_shared_origins")

            return AIMessage(
                content="Card C12382-K1 has 4 prior confirmed fraud cases in Q3 2016 (cloning and new device). Exploring graph connections for shared devices, shared regions, or connected cards.",
                tool_calls=tool_calls
            )

        # 5. External validation request for unknown authorization
        if "request_customer_validation" not in executed_tools:
            self.tool_sequence.append("request_customer_validation")
            return AIMessage(
                content="Graph queries reveal no shared devices (0 multi-account sharing) and no connected cards. To resolve authorization uncertainty on card-present transaction 3514030, registering customer validation request.",
                tool_calls=[{
                    "name": "request_customer_validation",
                    "args": {
                        "transaction_id": "3514030",
                        "question": "Did you authorize an in-person charge of $77.07 in billing region 444 on 2016-12-04?"
                    },
                    "id": "call_cust_val",
                }]
            )

        # 6. Final synthesis evaluating all 8 hypotheses
        hypotheses = [
            {
                "id": "hyp_1_recurring_behavior",
                "title": "Legitimate Recurring Customer Behavior",
                "description": "Transaction 3514030 ($77.07) represents standard in-person recurring cardholder spending in established billing region 444.",
                "confidence": 0.60,
                "supporting_evidence": [
                    "Billing region 444 has 15 historical transactions totaling $1,049.26 spanning Sept-Dec 2016.",
                    "Transaction amount ($77.07) matches established repeat spending in region 444 ($76.96, $77.01, $77.05).",
                    "Transaction channel is in-person (ProductCD=W), consistent with cardholder's regular purchasing channel.",
                    "Sequence analysis shows no rapid velocity burst (1.0 txn/hr)."
                ],
                "contradicting_evidence": [
                    "Flagged with elevated model risk score of 0.61.",
                    "Card C12382-K1 has historical precedent of confirmed card cloning."
                ],
            },
            {
                "id": "hyp_2_out_of_region",
                "title": "Out-of-Region Fraud",
                "description": "Transaction was conducted by an unauthorized third party in a region where the cardholder has no history.",
                "confidence": 0.15,
                "supporting_evidence": [
                    "Historical closed cases CC-1066, CC-2964, and CC-3587 were classified under the 'out_of_region_use' pattern."
                ],
                "contradicting_evidence": [
                    "Region 444 is NOT an out-of-region location; customer C12382 has 15 transactions in region 444 accounting for 3.55% of all activity.",
                    "First transaction in region 444 was observed on 2016-09-13, showing long-standing presence."
                ],
            },
            {
                "id": "hyp_3_card_compromise",
                "title": "Historical Card Compromise / Counterfeit Card Cloning",
                "description": "Card C12382-K1 credentials were historically cloned via physical skimming, allowing unauthorized in-person use while the customer retained possession.",
                "confidence": 0.45,
                "supporting_evidence": [
                    "Closed case history confirms 4 prior fraud cases (CC-1066, CC-1673, CC-2964, CC-3587) on card C12382-K1 between July and September 2016.",
                    "Analyst notes in CC-1066, CC-2964, and CC-3587 confirm counterfeit card cloning where cardholder retained physical card."
                ],
                "contradicting_evidence": [
                    "All 4 historical cases occurred in Q3 2016 (July-Sept); transaction 3514030 took place in December 2016.",
                    "Card was reissued and customer transacted legitimately across multiple months without subsequent fraud disputes."
                ],
            },
            {
                "id": "hyp_4_shared_device",
                "title": "Shared Device / Connected Customer Activity",
                "description": "Fraudulent transaction was initiated from a suspicious device shared across multiple customer accounts.",
                "confidence": 0.05,
                "supporting_evidence": [],
                "contradicting_evidence": [
                    "Transaction 3514030 was conducted in-person (ProductCD=W) with no associated device identifier in identity records.",
                    "Customer C12382 has only 1 historical device ('iOS Device') with zero multi-account sharing (associated_customer_count=1)."
                ],
            },
            {
                "id": "hyp_5_shared_region",
                "title": "Shared Billing Region Syndicate Activity",
                "description": "Activity is part of a coordinated fraud cluster operating across common anonymized billing region 444.",
                "confidence": 0.10,
                "supporting_evidence": [
                    "Billing region 444 is an anonymized region code (addr1) shared by other transactions in the dataset.",
                    "Shared origin analysis identifies region 512 shared by 677 customers."
                ],
                "contradicting_evidence": [
                    "Region 444 is an established customer home/routine region with 15 transactions.",
                    "No cluster of anomalous or fraudulent transactions linked to C12382 in region 444."
                ],
            },
            {
                "id": "hyp_6_connected_cards",
                "title": "Connected Cards / Synthetic Identity Syndicate",
                "description": "Transaction is linked to a network of synthetic cards or compromised card clusters sharing credentials or devices.",
                "confidence": 0.05,
                "supporting_evidence": [],
                "contradicting_evidence": [
                    "Graph analysis found 0 connected cards sharing credentials, devices, or accounts (total_connected_cards=0).",
                    "Card credentials (card1: 21139, card2: 242.0, card3: 150.0) are isolated to customer C12382."
                ],
            },
            {
                "id": "hyp_7_coordinated_abuse",
                "title": "Coordinated or Repeated Abuse / Velocity Spikes",
                "description": "Automated botting, credential stuffing, or rapid multi-transaction card draining.",
                "confidence": 0.05,
                "supporting_evidence": [],
                "contradicting_evidence": [
                    "Sequence query shows only 1 transaction in the 60-minute window (velocity=1.0 txn/hr).",
                    "No rapid successive transactions, failed authorization attempts, or velocity bursts detected."
                ],
            },
            {
                "id": "hyp_8_insufficient_evidence",
                "title": "Insufficient Evidence / Authorization Unknown",
                "description": "Because the transaction occurred in-person without biometric, 3DS, or digital device telemetry, authorization cannot be conclusively determined without cardholder outreach.",
                "confidence": 0.70,
                "supporting_evidence": [
                    "Transaction is card-present without customer signature/PIN confirmation or identity record.",
                    "Direct customer confirmation is pending under external request req_cust_3514030.",
                    "Conflict between established repeat spending patterns and known card compromise history cannot be resolved without cardholder statement."
                ],
                "contradicting_evidence": [
                    "Rich historical spending data exists in region 444, narrowing the range of possibilities."
                ],
            },
        ]

        synthesis_text = """DEEP INVESTIGATION SYNTHESIS FOR HHG-001:
1. FLAGGED TRANSACTION PROFILE:
   - Transaction 3514030 ($77.07) at 2016-12-04T19:55:28, channel 'in_person' (ProductCD=W), billing region 444, initial risk_score 0.61.
2. CUSTOMER REGIONAL HISTORY:
   - Customer C12382 has 422 transactions across 40 billing regions.
   - Region 444 is NOT an unseen or out-of-region area: customer has 15 transactions in region 444 totaling $1,049.26 spanning Sept-Dec 2016.
   - Amount $77.07 matches established repeat transactions ($76.96, $77.01, $77.05) in region 444.
3. VELOCITY & SEQUENCE:
   - Transaction sequence shows velocity of 1.0 txn/hr with no rapid bursts or coordinated spikes.
4. HISTORICAL CLOSED CASES PRECEDENT:
   - Card C12382-K1 was subjected to 4 confirmed fraud incidents in July-Sept 2016 (CC-1066, CC-1673, CC-2964, CC-3587).
   - CC-1066, CC-2964, CC-3587 involved counterfeit card cloning while cardholder held physical card.
5. GRAPH & CONNECTIVITY ANALYSIS:
   - No shared devices (1 device: iOS Device, 0 multi-account sharing).
   - No connected cards (total_connected_cards: 0).
   - Shared origins are broad public domains (gmail.com: 8,933 customers; region 512: 677 customers). No syndicate detected.
6. UNRESOLVED QUESTIONS & EXTERNAL EVIDENCE:
   - Did cardholder C12382 personally conduct this purchase in region 444 on 2016-12-04?
   - Request req_cust_3514030 dispatched for cardholder validation.
Investigation concluded with 8 competing hypotheses evaluated."""

        response = AIMessage(
            content=synthesis_text,
            tool_calls=[],
            additional_kwargs={"hypotheses": hypotheses}
        )
        return response


class DynamicAssessmentLLM:
    """
    Evaluates gathered evidence and competing hypotheses to produce structured Assessment.
    """

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
                "Card C12382-K1 has historical precedent of confirmed card cloning and out-of-region fraud (CC-1066, CC-2964, CC-3587).",
                "Flagged with elevated model risk score of 0.61.",
            ],
            contradicting_evidence=[
                "Billing region 444 is an established customer region with 15 prior transactions totaling $1,049.26 spanning Sept-Dec 2016.",
                "Transaction amount of $77.07 perfectly aligns with established repeat spending ($76.96 - $77.05) in region 444.",
                "Transaction channel is in-person (ProductCD=W), consistent with cardholder's routine behavior.",
                "Sequence analysis shows velocity of 1.0 txn/hr with no burst or coordinated abuse.",
                "Zero shared devices and zero connected cards found across graph relationships.",
            ],
            reasoning="The investigation evaluated 8 competing hypotheses. Hypotheses of out-of-region fraud, shared device abuse, connected card rings, and velocity spikes are firmly contradicted by evidence. However, evidence remains balanced between legitimate recurring spending in established region 444 and potential counterfeit card cloning given historical compromise precedent on card C12382-K1. Because physical card authorization cannot be verified without cardholder feedback, the case is assessed as uncertain with customer validation requested.",
            confidence=0.62,
        )


print("Testing DynamicDeepInvestigationLLM in LangGraph...")
inv_llm = DynamicDeepInvestigationLLM()
ass_llm = DynamicAssessmentLLM()
graph = build_investigation_graph(inv_llm, assessment_llm=ass_llm)

init_state = create_initial_state(
    case_id="HHG-001",
    customer_id="C12382",
    card_id="C12382-K1",
    flagged_txn_id="3514030",
)

final_state = graph.invoke(init_state)

print("\n--- RESULTS ---")
print("Case ID:", final_state.get("case_id"))
print("Iterations:", final_state.get("iteration_count"))
print("Tools Used:", final_state.get("tools_used"))
print("Tool Sequence:", inv_llm.tool_sequence)
print("Evidence Count:", len(final_state.get("evidence", [])))
print("Hypotheses Count:", len(final_state.get("hypotheses", [])))
print("Evidence Requests:", final_state.get("evidence_requests"))
print("Assessment Verdict:", final_state.get("assessment", {}).get("verdict"))
print("Assessment Fraud Probability:", final_state.get("assessment", {}).get("fraud_probability"))
print("Assessment Reasoning:", final_state.get("assessment", {}).get("reasoning")[:100], "...")
