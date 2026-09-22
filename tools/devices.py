"""
Device investigative tools.

Provides tools for inspecting device linkages, multi-account device sharing,
and customer device history over time. Retrieves factual observed graph data
without interpreting shared devices as fraud.
"""

from typing import Any
from langchain_core.tools import tool

from .hhgoa_data import unavailable


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
    return unavailable("device_neighbors_require_device_profile_id") | {
        "customer_id": customer_id,
        "card_id": card_id,
        "device_id": device_id,
    }


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
    return unavailable("identity_device_history_not_available_for_customer") | {"customer_id": str(customer_id).strip()}

