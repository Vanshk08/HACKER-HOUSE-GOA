"""
Policy decision schema for the fraud investigation system.
Defines the structured output format for the Policy Engine.
"""

from typing import Literal, TypedDict
from pydantic import BaseModel, Field

ActionType = Literal[
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "BLOCK_CARD",
    "CREATE_CASE",
    "FILE_REPORT",
    "CLOSE_NO_FRAUD",
    "MONITOR_CARD",
    "DECLINE_TRANSACTION",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "ESCALATE_TO_ANALYST",
]

CustomerResponseStatusType = Literal[
    "unknown",
    "confirmed",
    "denied",
    "no_response",
]

VALID_ACTIONS: set[str] = {
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "BLOCK_CARD",
    "CREATE_CASE",
    "FILE_REPORT",
    "CLOSE_NO_FRAUD",
    "MONITOR_CARD",
    "DECLINE_TRANSACTION",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "ESCALATE_TO_ANALYST",
}


class PolicyDecision(TypedDict, total=False):
    """
    Structured policy decision produced by the Policy Engine.
    """
    actions: list[str]
    primary_action: str | None
    matched_rules: list[str]
    rationale: str
    requires_customer_response: bool
    evidence_requests: list[dict]
    exposure: float
    affected_txn_ids: list[str]
    customer_response_status: str | None
    policy_conflicts: list[str]


class PolicyDecisionSchema(BaseModel):
    """
    Pydantic schema for policy decision validation and structured serialization.
    """
    actions: list[ActionType] = Field(
        default_factory=list,
        description="Deterministic list of operational actions determined by policy rules.",
    )
    primary_action: ActionType | None = Field(
        default=None,
        description="Highest priority operational action selected from actions.",
    )
    matched_rules: list[str] = Field(
        default_factory=list,
        description="Identifiers of all policy rules that matched (e.g., 'R1', 'GLOBAL_CREATE_CASE').",
    )
    rationale: str = Field(
        default="",
        description="Audit trail explaining why actions were selected based on matched rules and evidence.",
    )
    requires_customer_response: bool = Field(
        default=False,
        description="Whether this decision depends on awaiting cardholder communication.",
    )
    evidence_requests: list[dict] = Field(
        default_factory=list,
        description="Pending or registered external evidence requests.",
    )
    exposure: float = Field(
        default=0.0,
        description="Verified monetary exposure amount under policy evaluation.",
        ge=0.0,
    )
    affected_txn_ids: list[str] = Field(
        default_factory=list,
        description="Verified affected transaction IDs.",
    )
    customer_response_status: CustomerResponseStatusType | None = Field(
        default="unknown",
        description="Current state of customer communication: 'unknown', 'confirmed', 'denied', or 'no_response'.",
    )
    policy_conflicts: list[str] = Field(
        default_factory=list,
        description="Any conflicting conditions identified and resolved by policy hierarchy.",
    )
