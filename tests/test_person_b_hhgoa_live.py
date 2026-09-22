from agent.llm_engine import get_assessment_llm, get_investigator_llm
from agent.orchestrator import build_investigation_graph
from agent.state import create_initial_state


def test_hhg001_person_b_uses_hhgoa_evidence_end_to_end():
    graph = build_investigation_graph(
        get_investigator_llm(provider="mock"),
        assessment_llm=get_assessment_llm(provider="mock"),
    )
    state = create_initial_state(
        case_id="HHG-001",
        customer_id="C12382",
        card_id="C12382-K1",
        flagged_txn_id="3514030",
        trigger_type="risk_score",
        trigger_text="Transaction 3514030 scored 0.61.",
        risk_score=0.61,
    )

    final_state = graph.invoke(state)
    evidence_by_source = {item["source"]: item for item in final_state["evidence"]}
    transaction = evidence_by_source["get_transaction"]["data"]["result"]
    graph_result = evidence_by_source["investigate_transaction_graph"]["data"]["result"]

    assert transaction["backend_status"] == "hhgoa_ieee"
    assert transaction["amount"] == 77.07
    assert transaction["customer_id"] == "C12382"
    assert transaction["risk_score"] == 0.61
    assert graph_result["found"] is True
    assert graph_result["transaction"]["amount"] == 77.07
    assert graph_result["transaction"]["customer_id"] == "C12382"
    assert graph_result["transaction"]["risk_score"] == 0.61
    assert graph_result["region_evidence"]
    assert graph_result["similar_prior_cases"]
    assert graph_result["email_evidence"] == []
    assert "device_evidence" not in graph_result
    assert final_state["assessment"]
    assert final_state["policy_decision"]
