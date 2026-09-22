"""
Transaction investigative tools.

Provides tools for inspecting individual transactions and temporal transaction
sequences. These tools retrieve raw observed transaction data and compute sequence
metrics without interpreting fraud or making policy decisions.
"""

from typing import Any
from langchain_core.tools import tool

from .hhgoa_data import transaction, transaction_sequence


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
    return transaction(str(transaction_id).strip())


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
    return transaction_sequence(str(customer_id).strip(), str(transaction_id).strip(), window_minutes)

