"""
Closed case investigative tools.

Provides tools for querying historical closed cases to establish precedent context.
IMPORTANT: Historical cases are observational evidence and context, NEVER automatic
verdicts for the current case under investigation.
"""

from typing import Any
from langchain_core.tools import tool

from .data_store import DataStore


@tool
def get_similar_closed_cases(
    customer_id: str | None = None,
    card_id: str | None = None,
    pattern: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """
    Find historical closed investigations that may provide useful precedent.

    Search dimensions may include:
    - customer ID
    - card ID
    - observed pattern (e.g., 'rapid_succession', 'cross_region', 'card_testing')
    - billing region (anonymized addr1 code)

    IMPORTANT: Historical cases are evidence/context, NOT automatic verdicts
    for the current case.

    Args:
        customer_id: Optional customer identifier to query precedent cases.
        card_id: Optional card identifier to query precedent cases.
        pattern: Optional pattern name or tag to search similar case archetypes.
        region: Optional anonymized billing region code (addr1).

    Returns:
        A dictionary containing matched closed cases (case ID, customer ID,
        card ID, historical verdict, pattern, affected transaction IDs,
        exposure, actions, analyst notes), query criteria, and backend status.
    """
    ds = DataStore.get_instance()
    return ds.get_similar_closed_cases(
        customer_id=str(customer_id).strip() if customer_id else None,
        card_id=str(card_id).strip() if card_id else None,
        pattern=str(pattern).strip() if pattern else None,
        region=str(region).strip() if region else None,
    )


@tool
def get_closed_case(case_id: str) -> dict[str, Any]:
    """
    Retrieve the full details of a known historical closed case.

    Returns the available historical case information without changing or interpreting it.

    Args:
        case_id: Unique identifier for the closed case record.

    Returns:
        A dictionary containing the complete archived case file:
        case ID, customer ID, card ID, flagged transaction ID, historical verdict,
        pattern, exposure amount, affected transaction IDs, historical actions taken,
        evidence records, and analyst notes.
    """
    ds = DataStore.get_instance()
    return ds.get_closed_case(str(case_id).strip())

