"""
Scratch script to verify the general autonomous LLM across all 20 cases.
"""

import os
import sys
import csv
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.llm_engine import AutonomousInvestigatorLLM, AutonomousAssessmentLLM
from agent.state import create_initial_state
from agent.orchestrator import build_investigation_graph
from agent.policy import PolicyAgent
from tools.data_store import DataStore

ds = DataStore.get_instance()

with open("data/case_pack.csv", mode="r", encoding="utf-8") as f:
    cases = list(csv.DictReader(f))

results = []
for idx, c in enumerate(cases, 1):
    case_id = c["case_id"]
    cust_id = c["customer_id"]
    card_id = c["card_id"]
    txn_id = str(c["flagged_txn_id"])
    trigger_type = c["trigger_type"]
    trigger_text = c["trigger_text"]
    risk_score = float(c["risk_score"]) if c.get("risk_score") else None

    inv_llm = AutonomousInvestigatorLLM()
    ass_llm = AutonomousAssessmentLLM()
    policy_agent = PolicyAgent()

    graph = build_investigation_graph(inv_llm, assessment_llm=ass_llm, policy=policy_agent)

    init_state = create_initial_state(
        case_id=case_id,
        customer_id=cust_id,
        card_id=card_id,
        flagged_txn_id=txn_id,
        trigger_type=trigger_type,
        trigger_text=trigger_text,
        risk_score=risk_score,
    )

    final_state = graph.invoke(init_state)

    ass = final_state.get("assessment", {})
    pol = final_state.get("policy_decision", {})
    tools_used = final_state.get("tools_used", [])
    ev_count = len(final_state.get("evidence", []))
    iterations = final_state.get("iteration_count", 0)

    print(f"[{idx:02d}/20] {case_id} | Verdict: {ass.get('verdict'):<16} | Prob: {ass.get('fraud_probability'):.2f} | Exp: ${ass.get('exposure'):<8.2f} | Act: {str(pol.get('actions')):<45} | Tools: {len(tools_used)}")
