"""
Card investigative tools.

Provides tools for inspecting card historical activity, spending patterns,
and multi-hop graph connections to other cards via shared entities.
Retrieves factual observed data only without interpreting fraud.
"""

from typing import Any
from langchain_core.tools import tool

from .data_store import DataStore


@tool
def get_card_history(card_id: str) -> dict[str, Any]:
    """
    Retrieve historical activity for a card.

    Investigate:
    - transaction history
    - spending patterns
    - regions (anonymized addr1 codes)
    - channels
    - transaction timing
    - previous suspicious/confirmed cases if available

    Returns observations only; does not determine fraud.

    Args:
        card_id: Unique identifier for the payment card.

    Returns:
        A dictionary containing historical transaction records, spending metrics,
        observed regions/channels, previous cases, and backend status.
    """
    ds = DataStore.get_instance()
    return ds.get_card_history(str(card_id).strip())


@tool
def get_connected_cards(card_id: str) -> dict[str, Any]:
    """
    Find cards connected to the specified card through graph relationships.

    Possible connections:
    - shared device profile (DeviceProfile)
    - shared email domain (EmailDomain)
    - shared billing region (BillingRegion / addr1)
    - other graph relationships

    Returns connected card IDs, connection type, shared entity, relevant timestamps,
    and relevant evidence. Does NOT automatically treat a connection as fraud.

    Args:
        card_id: Unique identifier for the payment card.

    Returns:
        A dictionary containing connected cards, connection topologies,
        shared entities, and backend status.
    """
    ds = DataStore.get_instance()
    return ds.get_connected_cards(str(card_id).strip())

