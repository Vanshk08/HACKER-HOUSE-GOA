"""
Graph investigative tools.

Provides tools for multi-hop graph exploration, detecting shared origins across
entities (DeviceProfile, EmailDomain, BillingRegion), and discovering graph-connected
confirmed fraud cases. Retrieves factual topological connections without automatically
treating graph linkages as fraud.
"""

from typing import Any
from langchain_core.tools import tool

from .hhgoa_data import unavailable


@tool
def find_shared_origins(
    card_id: str | None = None,
    customer_id: str | None = None,
) -> dict[str, Any]:
    """
    Find graph entities shared by multiple customers or cards.

    Possible shared origin entity types:
    - DeviceProfile
    - EmailDomain
    - BillingRegion (anonymized addr1)

    Supports investigation of coordinated or shared-origin activity across entities.
    Do NOT automatically classify shared origin as fraud.

    Args:
        card_id: Optional card identifier to inspect shared graph neighbors.
        customer_id: Optional customer identifier to inspect shared graph neighbors.

    Returns:
        A dictionary containing shared entities, entity types, connected customers,
        connected cards, relevant transactions, timestamps, previous confirmed fraud
        connections where available, and backend status.
    """
    return unavailable("shared_origin_query_not_installed") | {"card_id": card_id, "customer_id": customer_id}


@tool
def find_related_fraud(
    card_id: str | None = None,
    customer_id: str | None = None,
    device_id: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """
    Find confirmed fraud cases connected through graph relationships.

    Possible relationships:
    - same card
    - same customer
    - same device (DeviceProfile)
    - same billing region (BillingRegion / addr1)
    - other graph connections

    Returns the actual relationship topologies and supporting case IDs.
    Does not turn the result into a fraud verdict.

    Args:
        card_id: Optional card identifier to inspect connected fraud.
        customer_id: Optional customer identifier to inspect connected fraud.
        device_id: Optional device identifier to inspect connected fraud.
        region: Optional billing region code (addr1) to inspect connected fraud.

    Returns:
        A dictionary containing related fraud cases, relationship types,
        connected entity IDs, supporting case IDs, and backend status.
    """
    return unavailable("related_fraud_query_not_installed") | {"card_id": card_id, "customer_id": customer_id, "device_id": device_id, "region": region}

