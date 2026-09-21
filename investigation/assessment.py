"""
Assessment data model for the fraud investigation system.
"""

from typing import Literal, TypedDict

VerdictType = Literal["confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"]


class Assessment(TypedDict, total=False):
    """
    Structured evidence-based assessment produced by the Assessment Agent.

    Represents the evaluation of gathered evidence, competing hypotheses,
    and historical context without making final policy decisions.
    """

    # Verdict: confirmed_fraud, suspected_fraud, uncertain, legitimate
    verdict: VerdictType

    # Evidence-based assessment produced from the investigation.
    # NOT the original case-pack risk_score and not a supervised model probability.
    fraud_probability: float

    # Category of fraud if applicable (e.g. account_takeover, card_cloning, None)
    fraud_type: str | None

    # Monetary exposure amount at risk
    exposure: float

    # Specific transaction IDs verified to be affected
    affected_txn_ids: list[str]

    # Specific observations supporting the verdict
    supporting_evidence: list[str]

    # Specific observations contradicting fraud or supporting legitimate activity
    contradicting_evidence: list[str]

    # Detailed synthesis explaining how evidence led to the assessment
    reasoning: str

    # Confidence in this assessment (0.0 - 1.0)
    confidence: float
