"""
Transaction investigative tools.

Provides tools for inspecting individual transactions and temporal transaction
sequences. These tools retrieve raw observed transaction data and compute sequence
metrics without interpreting fraud or making policy decisions.
"""

from typing import Any
from langchain_core.tools import tool

from .data_store import DataStore


@tool
def get_transaction(transaction_id: str) -> dict[str, Any]:
    """
    Retrieve complete information about one transaction.

    Investigates transaction attributes, customer/card references, amounts,
    channels, anonymized billing region (addr1), risk scores, and model features.
    Retrieves observed data only; does not interpret the transaction as fraud.

    Args:
        transaction_id: Unique identifier for the transaction (e.g., '3514030').

    Returns:
        A dictionary containing observed transaction data, attributes,
        derived calculations, and backend status.
    """
    ds = DataStore.get_instance()
    res = ds.get_transaction(str(transaction_id).strip())
    if res:
        return res

    return {
        "transaction_id": transaction_id,
        "customer_id": None,
        "card_id": None,
        "timestamp": None,
        "amount": None,
        "channel": None,
        "billing_region": None,
        "risk_score": None,
        "attributes": {},
        "observed_data": {"transaction_id": transaction_id, "raw_record": None},
        "derived_calculations": {},
        "unavailable_data": ["customer_id", "card_id", "timestamp", "amount", "channel", "billing_region", "risk_score"],
        "backend_status": "real_dataset",
        "backend_note": f"Transaction {transaction_id} not found in challenge dataset.",
    }


@tool
def get_transaction_sequence(
    customer_id: str,
    transaction_id: str,
    window_minutes: int = 60,
) -> dict[str, Any]:
    """
    Investigate transactions occurring before and after the specified transaction.

    Use this tool to investigate:
    - rapid transaction sequences
    - transaction velocity
    - possible card testing
    - region transitions
    - repeated payments
    - unusual transaction timing

    Retrieves factual sequence data and time deltas; does NOT classify patterns as fraud.

    Args:
        customer_id: Identifier for the customer whose sequence is being investigated.
        transaction_id: Target reference transaction ID.
        window_minutes: Time window in minutes before and after the target transaction (default: 60).

    Returns:
        A dictionary containing target transaction, previous transactions,
        subsequent transactions, time differences, and sequence observations.
    """
    ds = DataStore.get_instance()
    return ds.get_transaction_sequence(
        customer_id=str(customer_id).strip(),
        transaction_id=str(transaction_id).strip(),
        window_minutes=window_minutes,
    )

