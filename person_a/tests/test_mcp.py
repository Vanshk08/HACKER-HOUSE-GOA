from person_a.mcp.server import analyze_transaction


def test_mcp_analyze_transaction():
    result = analyze_transaction("832318")

    assert result["found"] is True
    assert result["transaction_id"] == "832318"
    assert "risk_assessment" in result
    assert "network_evidence" in result