"""
Region investigative tools.

Provides tools for inspecting customer activity within billing regions.
IMPORTANT: In the IEEE-CIS dataset, addr1 is an anonymized billing region code.
These tools treat addr1 as an opaque identifier and NEVER decode it into a city,
state, or real-world geographic location. Does not classify region changes as fraud.
"""

from typing import Any
from langchain_core.tools import tool

from .hhgoa_data import customer_regions, region_activity


@tool
def get_region_activity(
    customer_id: str,
    region: str,
) -> dict[str, Any]:
    """
    Determine the customer's historical activity in a specific billing region.

    Investigates:
    - transaction count in region
    - transaction IDs
    - timestamps
    - transaction amounts
    - first observed transaction
    - most recent transaction
    - relevant card activity in region

    IMPORTANT: addr1 is an anonymized billing region code. Do NOT decode it into
    a city or geographic location. This tool helps determine whether a region represents
    established behavior, unusual behavior, or is previously unseen.
    Do not automatically classify it as out-of-region fraud.

    Args:
        customer_id: Unique identifier for the customer account.
        region: Anonymized billing region code (addr1 value, e.g., '315', '299').

    Returns:
        A dictionary containing historical transactions, counts, timestamps,
        amounts, cards used in this region, and backend status.
    """
    return region_activity(str(customer_id).strip(), str(region).strip())


@tool
def get_customer_regions(customer_id: str) -> dict[str, Any]:
    """
    Retrieve all billing regions historically associated with the customer.

    Investigates:
    - region codes (anonymized addr1 codes)
    - transaction counts per region
    - first and last observed activity per region
    - relevant cards used in each region
    - relevant transactions in each region

    IMPORTANT: Do not infer real-world locations from anonymized region codes.

    Args:
        customer_id: Unique identifier for the customer account.

    Returns:
        A dictionary containing all historical billing regions, transaction counts,
        temporal spans, primary region calculations, and backend status.
    """
    return customer_regions(str(customer_id).strip())

