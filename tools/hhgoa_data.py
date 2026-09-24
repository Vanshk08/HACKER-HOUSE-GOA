"""TigerGraph and Local DuckDB data access layer for Person B fraud investigation."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from person_a.retrieval.tigergraph_client import TigerGraphFraudClient


_client: TigerGraphFraudClient | None = None


def _tg_available() -> bool:
    """Check if TigerGraph credentials and dependencies are available."""
    try:
        from person_a.retrieval.tigergraph_client import tg
        if tg is None:
            return False
        return bool(os.getenv("TG_HOST") and os.getenv("TG_SECRET"))
    except Exception:
        return False


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


def _norm(result: dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict):
        result["backend_status"] = "hhgoa_ieee"
    return result


def transaction(transaction_id: str) -> dict[str, Any]:
    if _tg_available():
        try:
            raw = client().get_transaction(transaction_id)
            records = _items(raw, "result")
            if records:
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
        except Exception:
            pass

    from .data_store import DataStore
    res = DataStore.get_instance().get_transaction(str(transaction_id).strip())
    if res is not None:
        return _norm(res)
    return {
        "transaction_id": transaction_id,
        "backend_status": "hhgoa_ieee",
        "backend_note": "Transaction not found in HHGOA_IEEE or local dataset.",
        "unavailable_data": ["customer_id", "amount", "timestamp", "channel", "risk_score"],
    }


def customer_history(customer_id: str) -> dict[str, Any]:
    if _tg_available():
        try:
            blocks = client().get_customer_history(customer_id)
            cards = _items(blocks, "cards")
            transactions = _items(blocks, "txns")
            if blocks:
                card_ids = [c.get("v_id") or _attrs(c).get("card_id") for c in cards]
                regions = set()
                channels = set()
                amounts = []
                recent_txns = []
                for tx in transactions:
                    attrs = _attrs(tx)
                    if attrs.get("addr1"):
                        regions.add(str(attrs["addr1"]))
                    if attrs.get("channel"):
                        channels.add(str(attrs["channel"]))
                    amt = attrs.get("TransactionAmt", attrs.get("amount"))
                    if amt is not None:
                        try:
                            amounts.append(float(amt))
                        except (ValueError, TypeError):
                            pass
                    if len(recent_txns) < 5:
                        recent_txns.append({
                            "transaction_id": tx.get("v_id") or attrs.get("TransactionID"),
                            "amount": amt,
                            "timestamp": attrs.get("ts"),
                            "channel": attrs.get("channel"),
                            "billing_region": str(attrs.get("addr1", "")),
                            "risk_score": attrs.get("risk_score"),
                        })

                spending_summary = {}
                if amounts:
                    spending_summary = {
                        "min_amount": round(min(amounts), 2),
                        "max_amount": round(max(amounts), 2),
                        "mean_amount": round(sum(amounts) / len(amounts), 2),
                    }

                return {
                    "customer_id": customer_id,
                    "cards": cards[:5],
                    "card_ids": card_ids,
                    "total_transactions": len(transactions),
                    "historical_regions": sorted(regions),
                    "historical_channels": sorted(channels),
                    "recent_transactions": recent_txns,
                    "spending_summary": spending_summary,
                    "backend_status": "hhgoa_ieee",
                }
        except Exception:
            pass

    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_customer_history(str(customer_id).strip()))


def customer_cards(customer_id: str) -> dict[str, Any]:
    if _tg_available():
        try:
            blocks = client().get_customer_history(customer_id)
            cards = _items(blocks, "cards")
            if cards:
                card_list = []
                for c in cards:
                    c_id = c.get("v_id") or _attrs(c).get("card_id")
                    card_list.append({
                        "card_id": c_id,
                        "card_type": _attrs(c).get("card4") or _attrs(c).get("card_type"),
                    })
                return {
                    "customer_id": customer_id,
                    "cards": card_list,
                    "card_count": len(card_list),
                    "backend_status": "hhgoa_ieee",
                }
        except Exception:
            pass

    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_customer_cards(str(customer_id).strip()))


def _resolve_card_id(card_id: str) -> str:
    if card_id.startswith("card:"):
        return card_id
    if "-K" in card_id:
        return ""
    return card_id


def card_history(card_id: str) -> dict[str, Any]:
    if _tg_available():
        try:
            resolved = _resolve_card_id(card_id)
            if resolved:
                blocks = client().get_card_history(resolved)
                if blocks:
                    txns = _items(blocks, "txns")
                    compact_txns = []
                    for t in txns[:5]:
                        attrs = _attrs(t)
                        compact_txns.append({
                            "transaction_id": t.get("v_id") or attrs.get("TransactionID"),
                            "amount": attrs.get("TransactionAmt", attrs.get("amount")),
                            "timestamp": attrs.get("ts"),
                            "channel": attrs.get("channel"),
                            "risk_score": attrs.get("risk_score"),
                        })
                    return {
                        "card_id": card_id,
                        "resolved_card_id": resolved,
                        "card": _items(blocks, "card")[:2],
                        "recent_transactions": compact_txns,
                        "total_transactions": len(txns),
                        "backend_status": "hhgoa_ieee",
                    }
        except Exception:
            pass

    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_card_history(str(card_id).strip()))


def related_transactions(card_id: str) -> dict[str, Any]:
    if _tg_available():
        try:
            resolved = _resolve_card_id(card_id)
            if resolved:
                blocks = client().get_related_transactions(resolved)
                txns = _items(blocks, "txns")
                return {
                    "card_id": card_id,
                    "transactions": txns[:10],
                    "related_transaction_count": len(txns),
                    "backend_status": "hhgoa_ieee",
                }
        except Exception:
            pass

    from .data_store import DataStore
    cid = card_id.split("-")[0] if "-" in card_id else card_id
    txns = DataStore.get_instance().query(
        "SELECT * FROM transactions WHERE customer_id = ? ORDER BY ts ASC LIMIT 50",
        [cid],
    )
    return {
        "card_id": card_id,
        "transactions": txns,
        "related_transaction_count": len(txns),
        "backend_status": "hhgoa_ieee",
    }


def _in_window(value: Any, start: datetime, end: datetime) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value))
        return start <= parsed <= end
    except (TypeError, ValueError):
        return False


def transaction_sequence(customer_id: str, transaction_id: str, window_minutes: int = 60) -> dict[str, Any]:
    if _tg_available():
        try:
            target = transaction(transaction_id)
            if target.get("timestamp"):
                card_id = target.get("card_id", "")
                related = related_transactions(card_id).get("transactions", []) if card_id else []
                if related:
                    target_time = datetime.fromisoformat(str(target["timestamp"]))
                    start, end = target_time - timedelta(minutes=window_minutes), target_time + timedelta(minutes=window_minutes)
                    selected = [t for t in related if _in_window(_attrs(t).get("ts"), start, end)]
                    return {
                        "customer_id": customer_id,
                        "target_transaction_id": transaction_id,
                        "target_transaction": target,
                        "previous_transactions": [t for t in selected if str(_attrs(t).get("TransactionID")) < str(transaction_id)],
                        "subsequent_transactions": [t for t in selected if str(_attrs(t).get("TransactionID")) > str(transaction_id)],
                        "backend_status": "hhgoa_ieee",
                    }
        except Exception:
            pass

    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_transaction_sequence(
        customer_id=str(customer_id).strip(),
        transaction_id=str(transaction_id).strip(),
        window_minutes=window_minutes,
    ))


def region_activity(customer_id: str, region: str) -> dict[str, Any]:
    if _tg_available():
        try:
            region_id = f"region:{region}|" if not str(region).startswith("region:") else str(region)
            blocks = client().get_region_neighbors(region_id)
            if blocks:
                txns = [t for t in _items(blocks, "txns") if _attrs(t).get("customer_id") == customer_id]
                compact_txns = []
                for t in txns[:5]:
                    attrs = _attrs(t)
                    compact_txns.append({
                        "transaction_id": t.get("v_id") or attrs.get("TransactionID"),
                        "amount": attrs.get("TransactionAmt", attrs.get("amount")),
                        "timestamp": attrs.get("ts"),
                        "channel": attrs.get("channel"),
                    })
                return {
                    "customer_id": customer_id,
                    "region": region,
                    "recent_transactions": compact_txns,
                    "transaction_count": len(txns),
                    "backend_status": "hhgoa_ieee",
                }
        except Exception:
            pass

    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_region_activity(str(customer_id).strip(), str(region).strip()))


def customer_regions(customer_id: str) -> dict[str, Any]:
    if _tg_available():
        try:
            blocks = client().get_customer_history(customer_id)
            transactions = _items(blocks, "txns")
            if transactions:
                regions: dict[str, int] = {}
                for tx in transactions:
                    region = _attrs(tx).get("addr1")
                    if region:
                        regions[str(region)] = regions.get(str(region), 0) + 1
                return {
                    "customer_id": customer_id,
                    "region_codes": sorted(regions),
                    "regions": [{"region_code": k, "transaction_count": v} for k, v in sorted(regions.items())],
                    "total_regions": len(regions),
                    "backend_status": "hhgoa_ieee",
                }
        except Exception:
            pass

    from .data_store import DataStore
    res = _norm(DataStore.get_instance().get_customer_regions(str(customer_id).strip()))
    float_codes = []
    for c in res.get("region_codes", []):
        try:
            fc = f"{float(c):.1f}"
            float_codes.append(fc)
        except (ValueError, TypeError):
            pass
    for fc in float_codes:
        if fc not in res["region_codes"]:
            res["region_codes"].append(fc)
    return res


def similar_closed_cases(
    customer_id: str | None = None,
    pattern: str | None = None,
    card_id: str | None = None,
    region: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    if _tg_available():
        try:
            blocks = client().get_similar_closed_cases(customer_id or "", pattern or "out_of_region_use")
            cases = _items(blocks, "cases")
            if cases:
                compact_cases = []
                verdicts = {}
                for c in cases:
                    attrs = _attrs(c)
                    outcome = attrs.get("outcome", c.get("verdict"))
                    if outcome:
                        verdicts[str(outcome)] = verdicts.get(str(outcome), 0) + 1
                    if len(compact_cases) < 5:
                        compact_cases.append({
                            "case_id": c.get("v_id") or attrs.get("case_id"),
                            "customer_id": attrs.get("customer_id"),
                            "card_id": attrs.get("card_id"),
                            "verdict": outcome,
                            "pattern": attrs.get("pattern"),
                            "exposure": attrs.get("exposure_usd"),
                            "analyst_notes": attrs.get("analyst_notes"),
                        })
                return {
                    "cases": compact_cases,
                    "total_matches": len(cases),
                    "historical_verdict_breakdown": verdicts,
                    "backend_status": "hhgoa_ieee",
                }
        except Exception:
            pass

    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_similar_closed_cases(
        customer_id=str(customer_id).strip() if customer_id else None,
        card_id=str(card_id).strip() if card_id else None,
        pattern=str(pattern).strip() if pattern else None,
        region=str(region).strip() if region else None,
    ))


def closed_case(case_id: str) -> dict[str, Any]:
    if _tg_available():
        try:
            blocks = client().get_case(case_id)
            cases = _items(blocks, "result")
            if cases:
                attrs = _attrs(cases[0])
                return {
                    "case_id": case_id,
                    "case": {
                        "case_id": case_id,
                        "customer_id": attrs.get("customer_id"),
                        "card_id": attrs.get("card_id"),
                        "verdict": attrs.get("outcome"),
                        "pattern": attrs.get("pattern"),
                        "exposure": attrs.get("exposure_usd"),
                        "analyst_notes": attrs.get("analyst_notes"),
                    },
                    "found": True,
                    "backend_status": "hhgoa_ieee",
                }
        except Exception:
            pass

    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_closed_case(str(case_id).strip()))


# ----------------------------------------------------------------------
# RESTORED INVESTIGATION TOOLS IMPLEMENTATIONS
# Backed by real data via DataStore, with TigerGraph preservation
# ----------------------------------------------------------------------

def connected_cards(card_id: str) -> dict[str, Any]:
    """Find cards connected to the specified card through graph relationships."""
    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_connected_cards(str(card_id).strip()))


def device_connections(
    customer_id: str | None = None,
    card_id: str | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Investigate device relationships across accounts and cards."""
    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_device_connections(
        customer_id=str(customer_id).strip() if customer_id else None,
        card_id=str(card_id).strip() if card_id else None,
        device_id=str(device_id).strip() if device_id else None,
    ))


def customer_device_history(customer_id: str) -> dict[str, Any]:
    """Retrieve devices historically associated with a customer."""
    from .data_store import DataStore
    return _norm(DataStore.get_instance().get_customer_device_history(str(customer_id).strip()))


def shared_origins(
    card_id: str | None = None,
    customer_id: str | None = None,
) -> dict[str, Any]:
    """Find graph entities shared by multiple customers or cards."""
    from .data_store import DataStore
    return _norm(DataStore.get_instance().find_shared_origins(
        card_id=str(card_id).strip() if card_id else None,
        customer_id=str(customer_id).strip() if customer_id else None,
    ))


def related_fraud(
    card_id: str | None = None,
    customer_id: str | None = None,
    device_id: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Find confirmed fraud cases connected through graph relationships."""
    from .data_store import DataStore
    return _norm(DataStore.get_instance().find_related_fraud(
        card_id=str(card_id).strip() if card_id else None,
        customer_id=str(customer_id).strip() if customer_id else None,
        device_id=str(device_id).strip() if device_id else None,
        region=str(region).strip() if region else None,
    ))


def unavailable(reason: str) -> dict[str, Any]:
    return {"backend_status": "hhgoa_ieee", "unavailable_data": [reason], "observed_data": []}
