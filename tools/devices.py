"""
Device investigative tools.

Provides tools for inspecting device linkages, multi-account device sharing,
and customer device history over time. Retrieves factual observed graph data
without interpreting shared devices as fraud.
"""

from typing import Any
from langchain_core.tools import tool

from .data_store import DataStore


@tool
def get_device_connections(
    customer_id: str | None = None,
    card_id: str | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    """
    Investigate device relationships across accounts and cards.

    Determine:
    - which customers are associated with the device
    - which cards are associated with the device
    - whether the device appears across multiple accounts
    - transaction activity associated with the device
    - historical fraud cases connected to the device where available

    Returns graph relationships and observations. Does NOT conclude that
    a shared device indicates fraud.

    Args:
        customer_id: Optional customer identifier to query associated devices.
        card_id: Optional card identifier to query associated devices.
        device_id: Optional device identifier (DeviceProfile/DeviceInfo) to query connections.

    Returns:
        A dictionary containing associated customers, cards, transactions,
        linked fraud cases, sharing metrics, and backend status.
    """
    ds = DataStore.get_instance()
    return ds.get_device_connections(
        customer_id=str(customer_id).strip() if customer_id else None,
        card_id=str(card_id).strip() if card_id else None,
        device_id=str(device_id).strip() if device_id else None,
    )


@tool
def get_customer_device_history(customer_id: str) -> dict[str, Any]:
    """
    Retrieve devices historically associated with a customer.

    Investigate:
    - first/last observed time for each device
    - frequency of use
    - whether a specific device was previously observed
    - changes in device configuration (DeviceInfo, DeviceType, OS, browser)
    - device history surrounding flagged transactions

    Supports investigation of hypotheses (sudden device change, unseen device,
    established device behavior). Does not interpret evidence as a final verdict.

    Args:
        customer_id: Unique identifier for the customer account.

    Returns:
        A dictionary containing historical device timelines, configurations,
        usage frequencies, and backend status.
    """
    ds = DataStore.get_instance()
    return ds.get_customer_device_history(str(customer_id).strip())

