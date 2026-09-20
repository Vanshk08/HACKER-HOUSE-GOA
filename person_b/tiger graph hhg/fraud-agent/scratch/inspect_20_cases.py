"""
Scratch script to inspect what data exists for all 20 cases in DuckDB.
"""

import os
import sys
import csv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.data_store import DataStore

ds = DataStore.get_instance()

with open("data/case_pack.csv", mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    cases = list(reader)

print(f"Total cases in case_pack: {len(cases)}")
print("=" * 80)

for c in cases:
    case_id = c["case_id"]
    cust_id = c["customer_id"]
    card_id = c["card_id"]
    txn_id = str(c["flagged_txn_id"])
    trigger = c["trigger_type"]
    score = c["risk_score"]

    tx = ds.get_transaction(txn_id)
    amount = tx.get("amount") if tx else None
    channel = tx.get("channel") if tx else None
    region = tx.get("billing_region") if tx else None

    # Check closed cases
    closed = ds.get_similar_closed_cases(customer_id=cust_id)
    closed_count = closed.get("total_matches", 0)

    # Check devices
    dev = ds.get_device_connections(customer_id=cust_id)
    dev_count = dev.get("derived_calculations", {}).get("associated_customer_count", 0)
    is_shared = dev.get("derived_calculations", {}).get("is_shared_across_multiple_accounts", False)

    print(f"{case_id} | Cust: {cust_id} | Card: {card_id} | Txn: {txn_id} | ${amount} | Ch: {channel} | Reg: {region} | Trig: {trigger} | Score: {score} | Closed: {closed_count} | DevShared: {is_shared}")
