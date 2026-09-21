"""
Evidence data model for the fraud investigation system.
"""

from typing import Any, TypedDict


class Evidence(TypedDict, total=False):
    """
    Persistent evidence observation discovered during investigation.
    """

    id: str
    source: str
    type: str
    description: str
    data: dict[str, Any]
    confidence: float
