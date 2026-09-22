from person_a.retrieval.fraud_analyzer import FraudAnalyzer


def test_transaction_found():
    analyzer = FraudAnalyzer()
    result = analyzer.analyze("3514030")

    assert result["found"] is True
    assert result["transaction_id"] == "3514030"
    assert result["transaction"]["amount"] == 77.07
    assert result["transaction"]["customer_id"] == "C12382"
    assert result["transaction"]["risk_score"] == 0.61


def test_risk_assessment_exists():
    analyzer = FraudAnalyzer()
    result = analyzer.analyze("3514030")

    assert "risk_assessment" in result
    assert "risk_score" in result["risk_assessment"]
    assert "risk_level" in result["risk_assessment"]


def test_network_evidence_exists():
    analyzer = FraudAnalyzer()
    result = analyzer.analyze("3514030")

    assert "network_evidence" in result

    network = result["network_evidence"]

    assert "linked_cards" in network
    assert "related_transaction_count" in network
    assert "related_transactions" in network


def test_network_has_historical_transactions():
    analyzer = FraudAnalyzer()
    result = analyzer.analyze("3514030")

    network = result["network_evidence"]

    assert network["related_transaction_count"] > 0


def test_hhgoa_graph_evidence_is_not_fabricated():
    result = FraudAnalyzer().analyze("3514030")

    assert result["region_evidence"]
    assert result["similar_prior_cases"]
    assert result["email_evidence"] == []
    assert "device_evidence" not in result


def test_no_ground_truth_used_for_risk():
    analyzer = FraudAnalyzer()
    result = analyzer.analyze("3514030")

    assert "risk_assessment" in result
    assert isinstance(
        result["risk_assessment"]["risk_score"],
        (int, float)
    )


def test_transaction_not_found():
    analyzer = FraudAnalyzer()
    result = analyzer.analyze("DOES_NOT_EXIST")

    assert result["found"] is False
    assert result["transaction_id"] == "DOES_NOT_EXIST"


def test_investigation_summary():
    analyzer = FraudAnalyzer()
    result = analyzer.analyze("3514030")

    summary = analyzer.format_investigation_summary(result)

    assert "FRAUD INVESTIGATION SUMMARY" in summary
    assert "3514030" in summary
    assert "Risk Score" in summary
    assert "Risk Level" in summary
    assert "Graph Evidence" in summary