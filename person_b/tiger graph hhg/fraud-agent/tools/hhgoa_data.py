"""TigerGraph-backed Person B data access for the HHGOA_IEEE graph."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from person_a.retrieval.tigergraph_client import TigerGraphFraudClient


_client: TigerGraphFraudClient | None = None


def client() -> TigerGraphFraudClient:
    global _client
    if _client is None:
        _client = TigerGraphFraudClient()
    return _client


def _items(blocks: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for block in blocks or []:
        result.extend(block.get(key, []) or [])
    return result


def _attrs(vertex: dict[str, Any]) -> dict[str, Any]:
    return vertex.get("attributes", {}) if isinstance(vertex, dict) else {}


def transaction(transaction_id: str) -> dict[str, Any]:
    raw = client().get_transaction(transaction_id)
    records = _items(raw, "result")
    if not records:
        return {
            "transaction_id": transaction_id,
            "backend_status": "hhgoa_ieee",
            "backend_note": "Transaction not found in HHGOA_IEEE.",
            "unavailable_data": ["customer_id", "amount", "timestamp", "channel", "risk_score"],
        }
    attrs = _attrs(records[0])
    return {
        "transaction_id": str(attrs.get("TransactionID", transaction_id)),
        "customer_id": attrs.get("customer_id"),
        "card_id": client().card_id_from_attributes(attrs),
        "timestamp": attrs.get("ts"),
        "amount": attrs.get("TransactionAmt"),
        "channel": attrs.get("channel"),
        "billing_region": attrs.get("addr1"),
        "risk_score": attrs.get("risk_score"),
        "attributes": attrs,
        "observed_data": attrs,
        "backend_status": "hhgoa_ieee",
    }


def customer_history(customer_id: str) -> dict[str, Any]:
    blocks = client().get_customer_history(customer_id)
    cards = _items(blocks, "cards")
    transactions = _items(blocks, "txns")
    return {
        "customer_id": customer_id,
        "cards": cards,
        "transactions": transactions,
        "total_transactions": len(transactions),
        "backend_status": "hhgoa_ieee",
        "observed_data": blocks,
    }


def customer_cards(customer_id: str) -> dict[str, Any]:
    history = customer_history(customer_id)
    return {
        "customer_id": customer_id,
        "cards": history["cards"],
        "card_count": len(history["cards"]),
        "backend_status": "hhgoa_ieee",
        "observed_data": history["observed_data"],
    }


def _resolve_card_id(card_id: str) -> str:
    if card_id.startswith("card:"):
        return card_id
    if "-K" in card_id:
        return ""
    return card_id


def card_history(card_id: str) -> dict[str, Any]:
    resolved = _resolve_card_id(card_id)
    if resolved:
        blocks = client().get_card_history(resolved)
        return {
            "card_id": card_id,
            "resolved_card_id": resolved,
            "card": _items(blocks, "card"),
            "transactions": _items(blocks, "txns"),
            "total_transactions": len(_items(blocks, "txns")),
            "backend_status": "hhgoa_ieee",
            "observed_data": blocks,
        }
    customer_id = card_id.split("-K", 1)[0]
    history = customer_history(customer_id)
    return {
        "card_id": card_id,
        "resolved_card_id": None,
        "cards": history["cards"],
        "transactions": history["transactions"],
        "total_transactions": len(history["transactions"]),
        "backend_status": "hhgoa_ieee",
        "backend_note": "Case-pack card ID has no direct graph key; customer history was used without inventing a card mapping.",
        "observed_data": history["observed_data"],
    }


def related_transactions(card_id: str) -> dict[str, Any]:
    resolved = _resolve_card_id(card_id)
    if not resolved:
        return {"card_id": card_id, "transactions": [], "backend_status": "hhgoa_ieee", "unavailable_data": ["graph_card_key"]}
    blocks = client().get_related_transactions(resolved)
    txns = _items(blocks, "txns")
    return {"card_id": card_id, "transactions": txns, "related_transaction_count": len(txns), "backend_status": "hhgoa_ieee", "observed_data": blocks}


def transaction_sequence(customer_id: str, transaction_id: str, window_minutes: int = 60) -> dict[str, Any]:
    target = transaction(transaction_id)
    if not target.get("timestamp"):
        return {"customer_id": customer_id, "target_transaction_id": transaction_id, "previous_transactions": [], "subsequent_transactions": [], "backend_status": "hhgoa_ieee"}
    card_id = target.get("card_id", "")
    related = related_transactions(card_id).get("transactions", []) if card_id else []
    target_time = datetime.fromisoformat(str(target["timestamp"]))
    start, end = target_time - timedelta(minutes=window_minutes), target_time + timedelta(minutes=window_minutes)
    selected = [t for t in related if _in_window(_attrs(t).get("ts"), start, end)]
    return {"customer_id": customer_id, "target_transaction_id": transaction_id, "target_transaction": target, "previous_transactions": [t for t in selected if str(_attrs(t).get("TransactionID")) < str(transaction_id)], "subsequent_transactions": [t for t in selected if str(_attrs(t).get("TransactionID")) > str(transaction_id)], "backend_status": "hhgoa_ieee"}


def _in_window(value: Any, start: datetime, end: datetime) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value))
        return start <= parsed <= end
    except (TypeError, ValueError):
        return False


def region_activity(customer_id: str, region: str) -> dict[str, Any]:
    region_id = f"region:{region}|" if not str(region).startswith("region:") else str(region)
    blocks = client().get_region_neighbors(region_id)
    txns = [t for t in _items(blocks, "txns") if _attrs(t).get("customer_id") == customer_id]
    return {"customer_id": customer_id, "region": region, "transactions": txns, "transaction_count": len(txns), "backend_status": "hhgoa_ieee", "observed_data": blocks}


def customer_regions(customer_id: str) -> dict[str, Any]:
    history = customer_history(customer_id)
    regions: dict[str, int] = {}
    for tx in history["transactions"]:
        region = _attrs(tx).get("addr1")
        if region:
            regions[str(region)] = regions.get(str(region), 0) + 1
    return {"customer_id": customer_id, "region_codes": sorted(regions), "regions": [{"region_code": k, "transaction_count": v} for k, v in regions.items()], "backend_status": "hhgoa_ieee", "observed_data": history["observed_data"]}


def similar_closed_cases(customer_id: str | None = None, pattern: str | None = None, **_: Any) -> dict[str, Any]:
    blocks = client().get_similar_closed_cases(customer_id or "", pattern or "out_of_region_use")
    cases = _items(blocks, "cases")
    details = []
    if cases:
        case_id = _attrs(cases[0]).get("case_id", cases[0].get("v_id"))
        if case_id:
            details = _items(client().get_case(str(case_id)), "result")
    return {"cases": cases, "case_details": details, "total_matches": len(cases), "backend_status": "hhgoa_ieee", "observed_data": blocks}


def closed_case(case_id: str) -> dict[str, Any]:
    blocks = client().get_case(case_id)
    cases = _items(blocks, "result")
    return {"case_id": case_id, "case": cases[0] if cases else None, "found": bool(cases), "backend_status": "hhgoa_ieee", "observed_data": blocks}


def unavailable(reason: str) -> dict[str, Any]:
    return {"backend_status": "hhgoa_ieee", "unavailable_data": [reason], "observed_data": []}
