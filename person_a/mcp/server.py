import os
import sys

# Make the project root importable when MCP Inspector loads this file directly.
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp.server import MCPServer

from person_a.retrieval.fraud_analyzer import FraudAnalyzer


mcp = MCPServer("TigerGraph Fraud Investigator")

_analyzer = None


def get_analyzer():
    global _analyzer

    if _analyzer is None:
        _analyzer = FraudAnalyzer()

    return _analyzer


@mcp.tool()
def analyze_transaction(transaction_id: str) -> dict:
    """
    Investigate a payment transaction using TigerGraph
    and return fraud-related signals and graph context.
    """
    return get_analyzer().analyze(transaction_id)


if __name__ == "__main__":
    mcp.run()