from langchain_core.tools import tool

from person_a.retrieval.fraud_analyzer import FraudAnalyzer


_analyzer = None


def _get_analyzer():
    global _analyzer

    if _analyzer is None:
        _analyzer = FraudAnalyzer()

    return _analyzer


@tool
def investigate_transaction_graph(transaction_id: str) -> dict:
    """
    Investigate a transaction using TigerGraph.

    Returns graph-based investigation evidence including:
    - transaction information
    - graph features
    - linked cards
    - historical related transactions
    - fraud signals

    This tool provides evidence only.
    It does not make the final fraud or policy decision.
    """

    return _get_analyzer().analyze(transaction_id)