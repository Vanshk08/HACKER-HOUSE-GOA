"""Detailed trace of investigate_transaction_graph execution.

Tests the existing tool directly with transaction_id '9998', tracing each hop:
investigate_transaction_graph -> Person A MCP -> FraudAnalyzer -> TigerGraphFraudClient -> TigerGraph
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from tools.tigergraph_fraud import investigate_transaction_graph


def trace_tool(graph_target: str | None = None):
    if graph_target:
        os.environ["HHGOA_GRAPH"] = graph_target
    else:
        os.environ.pop("HHGOA_GRAPH", None)

    print(f"\n{'='*70}")
    print(f"RUNNING investigate_transaction_graph(transaction_id='9998')")
    print(f"Environment TG_GRAPH: {os.getenv('TG_GRAPH')}")
    print(f"Environment HHGOA_GRAPH: {os.getenv('HHGOA_GRAPH', '<unset, defaults to HHGOA_IEEE>')}")
    print(f"{'='*70}")

    result = investigate_transaction_graph.invoke({"transaction_id": "9998"})
    print("Invocation Completed Successfully.")
    print("Result Keys:", list(result.keys()))
    print("Found:", result.get("found"))
    if result.get("found"):
        print("Transaction Data:", result.get("transaction"))
        print("Graph Features:", result.get("graph_features"))
        print("Risk Assessment:", result.get("risk_assessment"))
    else:
        print("Message:", result.get("message"))
    return result


if __name__ == "__main__":
    print("--- 1. Default Configuration (HHGOA_GRAPH unset) ---")
    trace_tool(graph_target=None)

    print("\n--- 2. Directed to Transaction_Fraud (HHGOA_GRAPH=Transaction_Fraud) ---")
    trace_tool(graph_target="Transaction_Fraud")
