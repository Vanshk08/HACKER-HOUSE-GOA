from person_a.mcp.server import analyze_transaction


def test_mcp_analyze_transaction():
    result = analyze_transaction("3514030")

    assert result["found"] is True
    assert result["transaction_id"] == "3514030"
    assert result["transaction"]["amount"] == 77.07
    assert result["transaction"]["customer_id"] == "C12382"
    assert result["transaction"]["risk_score"] == 0.61
    assert "risk_assessment" in result
    assert "network_evidence" in result
    assert result["region_evidence"]
    assert result["similar_prior_cases"]
    assert result["email_evidence"] == []
    assert "device_evidence" not in result