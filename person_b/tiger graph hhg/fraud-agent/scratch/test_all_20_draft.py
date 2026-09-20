"""
Scratch script to test the generic autonomous investigator and assessment LLM on all 20 cases.
"""

import os
import sys
import csv
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import AIMessage
from agent.state import create_initial_state
from agent.orchestrator import build_investigation_graph
from agent.assessment import AssessmentSchema
from agent.policy import PolicyAgent
from tools.data_store import DataStore


class AutonomousInvestigatorLLM:
    """
    Autonomous investigator LLM that dynamically inspects evidence
    and decides what tools to call for any given case.
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

        # Extract case info from first HumanMessage
        first_content = ""
        for msg in messages:
            if type(msg).__name__ == "HumanMessage":
                first_content = msg.content
                break

        # Parse case context
        case_id = ""
        cust_id = ""
        card_id = ""
        flagged_txn_id = ""
        for line in first_content.splitlines():
            line = line.strip()
            if line.startswith("case_id:"):
                case_id = line.split(":", 1)[1].strip()
            elif line.startswith("customer_id:"):
                cust_id = line.split(":", 1)[1].strip()
            elif line.startswith("card_id:"):
                card_id = line.split(":", 1)[1].strip()
            elif line.startswith("flagged_txn_id:"):
                flagged_txn_id = line.split(":", 1)[1].strip()

        # Step 1: Inspect flagged transaction
        if "get_transaction" not in executed_tools:
            self.tool_sequence.append("get_transaction")
            return AIMessage(
                content=f"Investigating flagged transaction {flagged_txn_id} to examine amount, channel, and billing region.",
                tool_calls=[{
                    "name": "get_transaction",
                    "args": {"transaction_id": flagged_txn_id},
                    "id": f"call_tx_{flagged_txn_id}",
                }]
            )

        # Step 2: Customer history, regions, and sequence
        missing_cust = [t for t in ["get_customer_history", "get_customer_regions", "get_transaction_sequence"] if t not in executed_tools]
        if missing_cust:
            tool_calls = []
            if "get_customer_history" not in executed_tools:
                tool_calls.append({"name": "get_customer_history", "args": {"customer_id": cust_id}, "id": "call_ch"})
                self.tool_sequence.append("get_customer_history")
            if "get_customer_regions" not in executed_tools:
                tool_calls.append({"name": "get_customer_regions", "args": {"customer_id": cust_id}, "id": "call_cr"})
                self.tool_sequence.append("get_customer_regions")
            if "get_transaction_sequence" not in executed_tools:
                tool_calls.append({"name": "get_transaction_sequence", "args": {"customer_id": cust_id, "transaction_id": flagged_txn_id}, "id": "call_ts"})
                self.tool_sequence.append("get_transaction_sequence")

            return AIMessage(
                content=f"Examining customer {cust_id} historical spending, billing regions, and sequence velocity.",
                tool_calls=tool_calls
            )

        # Step 3: Card history and closed cases
        missing_card = [t for t in ["get_card_history", "get_similar_closed_cases"] if t not in executed_tools]
        if missing_card:
            tool_calls = []
            if "get_card_history" not in executed_tools:
                tool_calls.append({"name": "get_card_history", "args": {"card_id": card_id}, "id": "call_card_h"})
                self.tool_sequence.append("get_card_history")
            if "get_similar_closed_cases" not in executed_tools:
                tool_calls.append({"name": "get_similar_closed_cases", "args": {"customer_id": cust_id}, "id": "call_scc"})
                self.tool_sequence.append("get_similar_closed_cases")

            return AIMessage(
                content=f"Checking card {card_id} history and searching historical closed cases for behavioral precedents.",
                tool_calls=tool_calls
            )

        # Step 4: Graph connectivity (devices and shared origins)
        missing_graph = [t for t in ["get_device_connections", "find_shared_origins"] if t not in executed_tools]
        if missing_graph:
            tool_calls = []
            if "get_device_connections" not in executed_tools:
                tool_calls.append({"name": "get_device_connections", "args": {"customer_id": cust_id}, "id": "call_dc"})
                self.tool_sequence.append("get_device_connections")
            if "find_shared_origins" not in executed_tools:
                tool_calls.append({"name": "find_shared_origins", "args": {"customer_id": cust_id}, "id": "call_so"})
                self.tool_sequence.append("find_shared_origins")

            return AIMessage(
                content=f"Exploring graph connections for shared devices, shared origins, or connected cards for {cust_id}.",
                tool_calls=tool_calls
            )

        # Step 5: External evidence request if authorization is unknown
        # Check if customer already reported/disputed in trigger
        is_customer_reported = "customer_report" in first_content or "never made this" in first_content.lower()
        if not is_customer_reported and "request_customer_validation" not in executed_tools:
            self.tool_sequence.append("request_customer_validation")
            return AIMessage(
                content=f"Customer authorization is unconfirmed. Registering customer validation request for transaction {flagged_txn_id}.",
                tool_calls=[{
                    "name": "request_customer_validation",
                    "args": {
                        "transaction_id": flagged_txn_id,
                        "question": f"Did you authorize transaction {flagged_txn_id}?"
                    },
                    "id": "call_req_val",
                }]
            )

        # Step 6: Conclude investigation with synthesis and hypotheses
        hypotheses = [
            {
                "id": "hyp_1_recurring_behavior",
                "title": "Legitimate Recurring Customer Behavior",
                "description": "Transaction represents routine customer spending consistent with established history.",
                "confidence": 0.50,
                "supporting_evidence": ["Customer historical activity exists in billing regions."],
                "contradicting_evidence": ["Flagged by monitoring rules."],
            },
            {
                "id": "hyp_2_unauthorized_fraud",
                "title": "Unauthorized Third-Party Fraud",
                "description": "Transaction was conducted by an unauthorized party.",
                "confidence": 0.50,
                "supporting_evidence": ["Flagged transaction requires investigation."],
                "contradicting_evidence": [],
            },
        ]

        return AIMessage(
            content=f"Investigation concluded for case {case_id}. All relevant tools executed and hypotheses evaluated.",
            tool_calls=[],
            additional_kwargs={"hypotheses": hypotheses}
        )


class AutonomousAssessmentLLM:
    """
    Autonomous Assessment LLM evaluating gathered evidence and producing
    a structured AssessmentSchema adhering to the 9-field schema.
    """

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        content = ""
        for m in messages:
            if hasattr(m, "content"):
                content += str(m.content) + "\n"

        # Determine trigger from content
        is_customer_reported = "trigger_type: customer_report" in content or "trigger_text: customer c" in content.lower()
        
        # Extract amount from content if present
        import re
        amt_match = re.search(r"'amount':\s*([0-9]+\.?[0-9]*)", content)
        exposure = float(amt_match.group(1)) if amt_match else 0.0

        txn_match = re.search(r"'transaction_id':\s*'([0-9]+)'", content)
        affected_txn_ids = [txn_match.group(1)] if txn_match else []

        if is_customer_reported:
            # Customer explicitly disputed/denied transaction
            verdict = "confirmed_fraud"
            fraud_prob = 0.92
            fraud_type = "card_not_present_unauthorized" if "'channel': 'online'" in content else "card_cloning"
            supporting = ["Cardholder explicitly reported and disputed the transaction as unauthorized."]
            contradicting = ["Account had prior legitimate activity."]
            reasoning = "Cardholder reported never making this purchase. In conjunction with transaction observations, this confirms unauthorized activity."
            confidence = 0.90
        else:
            # Risk score or analyst request
            # Check if region is previously observed
            # In region activity, check if transaction_count > 1 or is_previously_observed: True
            is_prev_observed = "'is_previously_observed': True" in content
            has_closed_cases = "CC-" in content

            if is_prev_observed:
                verdict = "uncertain"
                fraud_prob = 0.42
                fraud_type = None
                supporting = ["Transaction was flagged by risk monitoring system."]
                if has_closed_cases:
                    supporting.append("Historical precedent of closed fraud cases on customer card.")
                contradicting = [
                    "Transaction occurred in an established customer billing region.",
                    "No velocity anomaly or rapid successive attempts detected.",
                ]
                reasoning = "Transaction occurred in an established billing region with historical consistency, but authorization remains unconfirmed. Awaiting customer confirmation."
                confidence = 0.62
            else:
                verdict = "suspected_fraud"
                fraud_prob = 0.74
                fraud_type = "out_of_region_use" if "'channel': 'in_person'" in content else "card_not_present_new_device"
                supporting = [
                    "Transaction occurred in an unseen or novel region without historical precedent.",
                    "Elevated risk score detected.",
                ]
                contradicting = ["Card was previously active and customer has valid account history."]
                reasoning = "Transaction exhibits out-of-pattern characteristics with elevated risk score and lack of regional precedent. Suspected fraud pending customer response."
                confidence = 0.75

        return AssessmentSchema(
            verdict=verdict,
            fraud_probability=fraud_prob,
            fraud_type=fraud_type,
            exposure=exposure,
            affected_txn_ids=affected_txn_ids,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            reasoning=reasoning,
            confidence=confidence,
        )



print("Testing all 20 cases...")
ds = DataStore.get_instance()
with open("data/case_pack.csv", mode="r", encoding="utf-8") as f:
    cases = list(csv.DictReader(f))

for idx, c in enumerate(cases, 1):
    case_id = c["case_id"]
    cust_id = c["customer_id"]
    card_id = c["card_id"]
    txn_id = str(c["flagged_txn_id"])
    trigger = c["trigger_type"]
    score = float(c["risk_score"]) if c.get("risk_score") else 0.0

    inv_llm = AutonomousInvestigatorLLM()
    ass_llm = AutonomousAssessmentLLM()
    policy_agent = PolicyAgent()

    graph = build_investigation_graph(inv_llm, assessment_llm=ass_llm, policy=policy_agent)

    init_state = create_initial_state(
        case_id=case_id,
        customer_id=cust_id,
        card_id=card_id,
        flagged_txn_id=txn_id,
    )
    # If customer reported, customer response is denied
    if trigger == "customer_report":
        init_state["customer_response_status"] = "denied"
        init_state["customer_denied"] = True

    final_state = graph.invoke(init_state)

    ass = final_state.get("assessment", {})
    pol = final_state.get("policy_decision", {})

    print(f"[{idx:02d}/20] {case_id} | Verdict: {ass.get('verdict'):<16} | Prob: {ass.get('fraud_probability'):.2f} | Exp: ${ass.get('exposure'):<7.2f} | Primary: {pol.get('primary_action')} | Rules: {pol.get('matched_rules')}")
