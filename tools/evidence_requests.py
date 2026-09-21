"""
External evidence request investigative tools.

Provides tools for creating external evidence requests (customer validation and
step-up authentication). These tools record pending requests without making policy
decisions or fraud verdicts. The policy engine handles the outcomes once responses
are received.
"""

from datetime import datetime, timezone
from typing import Any
from langchain_core.tools import tool


@tool
def request_customer_validation(
    transaction_id: str,
    question: str,
) -> dict[str, Any]:
    """
    Create a customer confirmation request.

    Dispatches or registers a formal verification question to the customer regarding
    a specific transaction.

    This tool does NOT decide what happens if the customer confirms or denies the
    transaction; the policy engine handles all decision rules.

    Args:
        transaction_id: Identifier of the transaction requiring customer verification.
        question: Specific verification question (e.g., 'Did you authorize this transaction?').

    Returns:
        A dictionary containing the pending customer confirmation request descriptor.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "request_type": "customer_confirmation",
        "transaction_id": transaction_id,
        "question": question,
        "status": "pending",
        "created_at": timestamp,
        "request_id": f"req_cust_{transaction_id}",
        "metadata": {
            "channel": "customer_outreach",
            "awaiting_response": True,
        },
    }


@tool
def request_step_up(
    transaction_id: str,
    reason: str,
) -> dict[str, Any]:
    """
    Request additional authentication for a transaction.

    Registers a step-up authentication challenge (such as 3D Secure, OTP,
    or biometric verification) for a transaction under investigation.

    Does not make a fraud verdict or decide downstream card blocking actions.

    Args:
        transaction_id: Identifier of the transaction requiring step-up authentication.
        reason: Factual investigation rationale explaining why step-up authentication is requested.

    Returns:
        A dictionary containing the pending step-up authentication request descriptor.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "request_type": "step_up_authentication",
        "transaction_id": transaction_id,
        "reason": reason,
        "status": "pending",
        "created_at": timestamp,
        "request_id": f"req_stepup_{transaction_id}",
        "metadata": {
            "channel": "step_up_challenge",
            "awaiting_response": True,
        },
    }
