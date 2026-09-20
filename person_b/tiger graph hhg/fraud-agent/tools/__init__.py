"""
Investigative Tool Layer for Fraud Investigation Agent.

This module provides all 16 focused investigative tools for the fraud investigation
agent. Each tool retrieves or analyzes evidence without making policy decisions,
interpreting final fraud verdicts, or executing LLM calls internally.

All tools are decorated with `@tool` from langchain_core.tools and can be bound
directly to the LLM:
    llm_with_tools = llm.bind_tools(INVESTIGATION_TOOLS)
"""

from .transactions import (
    get_transaction,
    get_transaction_sequence,
)
from .customers import (
    get_customer_history,
    get_customer_cards,
)
from .cards import (
    get_card_history,
    get_connected_cards,
)
from .devices import (
    get_device_connections,
    get_customer_device_history,
)
from .regions import (
    get_region_activity,
    get_customer_regions,
)
from .closed_cases import (
    get_similar_closed_cases,
    get_closed_case,
)
from .graph import (
    find_shared_origins,
    find_related_fraud,
)
from .evidence_requests import (
    request_customer_validation,
    request_step_up,
)

INVESTIGATION_TOOLS = [
    get_transaction,
    get_transaction_sequence,

    get_customer_history,
    get_customer_cards,

    get_card_history,
    get_connected_cards,

    get_device_connections,
    get_customer_device_history,

    get_region_activity,
    get_customer_regions,

    get_similar_closed_cases,
    get_closed_case,

    find_shared_origins,
    find_related_fraud,

    request_customer_validation,
    request_step_up,
]

__all__ = [
    "INVESTIGATION_TOOLS",
    "get_transaction",
    "get_transaction_sequence",
    "get_customer_history",
    "get_customer_cards",
    "get_card_history",
    "get_connected_cards",
    "get_device_connections",
    "get_customer_device_history",
    "get_region_activity",
    "get_customer_regions",
    "get_similar_closed_cases",
    "get_closed_case",
    "find_shared_origins",
    "find_related_fraud",
    "request_customer_validation",
    "request_step_up",
]
