"""
Customer investigative tools.

Provides tools for inspecting customer historical activity, spending patterns,
associated cards, devices, channels, and normal behavior profiles.
Retrieves factual observed data only without interpreting fraud.
"""

from typing import Any
from langchain_core.tools import tool

from .data_store import DataStore


@tool
def get_customer_history(customer_id: str) -> dict[str, Any]:
    """
    Retrieve historical activity for a customer.

    Investigate:
    - historical spending behavior
    - normal transaction amounts
    - normal regions (anonymized addr1 codes)
    - normal channels
    - transaction frequency
    - historical cards
    - historical devices where available

    Returns observations and raw data. Does not interpret fraud.

    Args:
        customer_id: Unique identifier for the customer account.

    Returns:
        A dictionary containing observed historical customer data,
        behavioral summary calculations, and backend status.
    """
    ds = DataStore.get_instance()
    return ds.get_customer_history(str(customer_id).strip())


@tool
def get_customer_cards(customer_id: str) -> dict[str, Any]:
    """
    Find all cards associated with the customer.

    Investigate:
    - customer ID
    - card IDs
    - transaction counts per card
    - relevant historical information

    Does not determine whether the cards are fraudulent.

    Args:
        customer_id: Unique identifier for the customer account.

    Returns:
        A dictionary containing associated cards, transaction counts,
        historical summaries, and backend status.
    """
    ds = DataStore.get_instance()
    return ds.get_customer_cards(str(customer_id).strip())

