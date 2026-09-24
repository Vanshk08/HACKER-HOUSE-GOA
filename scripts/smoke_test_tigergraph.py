"""Temporary smoke test to verify TigerGraph integration independently.

This script:
1. Loads the existing .env file.
2. Connects to TigerGraph using the existing TigerGraphFraudClient.
3. Targets the existing TigerGraph graph: Transaction_Fraud (from TG_GRAPH).
4. Executes ONE simple real query against the graph.
5. Prints:
   - connection success/failure
   - graph name
   - query success/failure
   - number of returned records
   - a small sanitized sample of the returned records
Does NOT print TG_SECRET or any API keys.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure fraud-agent project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 1. Load existing .env
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from person_a.retrieval.tigergraph_client import TigerGraphFraudClient


def run_smoke_test():
    # 2. Check environment credentials without printing secret
    host = os.getenv("TG_HOST")
    has_secret = bool(os.getenv("TG_SECRET"))
    graph_name = os.getenv("TG_GRAPH", "Transaction_Fraud")

    print("=" * 60)
    print("TIGERGRAPH INTEGRATION SMOKE TEST")
    print("=" * 60)

    print(f"TG_HOST configured: {bool(host)}")
    print(f"TG_SECRET configured: {has_secret}")
    print(f"Target Graph Name: {graph_name}")

    if not host or not has_secret:
        print("Connection Status: FAILED (TG_HOST or TG_SECRET missing in .env)")
        return False

    # 3. Connect to TigerGraph using existing client
    try:
        client = TigerGraphFraudClient(graph=graph_name)
    except Exception as e:
        print(f"Connection Status: FAILED ({type(e).__name__}: {e})")
        return False

    if client.conn is None:
        print("Connection Status: FAILED (Unable to establish TigerGraph connection or acquire auth token)")
        return False

    print("Connection Status: SUCCESS")
    print(f"Active Graph Name: {client.graph}")

    # 4. Execute ONE simple real query against the graph
    # We call the existing client method get_transaction('9998') which executes
    # the installed query 'fraud_transaction_profile' on Transaction_Fraud.
    query_name = "fraud_transaction_profile"
    txn_id = "9998"
    print(f"Executing Query: {query_name}(transaction_id='{txn_id}') via client.get_transaction('{txn_id}')")

    try:
        raw_result = client.get_transaction(txn_id)
        query_success = bool(raw_result and isinstance(raw_result, list))
    except Exception as e:
        print(f"Query Status: FAILED ({type(e).__name__}: {e})")
        return False

    if not query_success:
        print("Query Status: FAILED (Empty or unexpected response format)")
        return False

    print("Query Status: SUCCESS")

    # 5. Extract records and record count
    # TigerGraph installed queries return: [{'result': [{...}, ...]}]
    records = []
    if raw_result and isinstance(raw_result, list):
        first_block = raw_result[0]
        if isinstance(first_block, dict) and "result" in first_block:
            records = first_block["result"]
        else:
            records = raw_result

    print(f"Number of Returned Records: {len(records)}")

    # 6. Print a small sanitized sample of the returned records
    if records:
        sample_item = records[0]
        v_id = sample_item.get("v_id") if isinstance(sample_item, dict) else None
        v_type = sample_item.get("v_type") if isinstance(sample_item, dict) else None
        attrs = sample_item.get("attributes", {}) if isinstance(sample_item, dict) else {}

        # Sanitize to include only non-sensitive domain attributes
        sanitized_sample = {
            "v_id": v_id,
            "v_type": v_type,
            "amount": attrs.get("amount"),
            "transaction_time": attrs.get("transaction_time"),
            "is_fraud": attrs.get("is_fraud"),
            "mer_pagerank": attrs.get("mer_pagerank"),
            "cd_pagerank": attrs.get("cd_pagerank"),
        }
        print("Sanitized Sample Record:")
        print(sanitized_sample)
    else:
        print("Sanitized Sample Record: None")

    print("=" * 60)
    print("SMOKE TEST RESULT: PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
