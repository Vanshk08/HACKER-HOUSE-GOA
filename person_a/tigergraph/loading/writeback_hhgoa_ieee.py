"""Guarded case writeback for the separate HHGOA_IEEE graph.

This module never writes to the legacy Transaction_Fraud graph. It writes only
case vertices and authoritative ClosedCase-to-Transaction edges. Card/device
case edges are intentionally omitted until a verified source mapping exists.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

import pyTigerGraph as tg
from dotenv import load_dotenv


TARGET_GRAPH = "HHGOA_IEEE"


def _client() -> tg.TigerGraphConnection:
    load_dotenv()
    graph = os.getenv("HHGOA_GRAPH", TARGET_GRAPH)
    if graph != TARGET_GRAPH:
        raise ValueError(f"Refusing writeback to unexpected graph: {graph}")
    host = os.getenv("TG_HOST")
    secret = os.getenv("TG_SECRET")
    if not host or not secret:
        raise ValueError("TG_HOST and TG_SECRET are required")
    client = tg.TigerGraphConnection(host=host, graphname=graph, gsqlSecret=secret)
    client.getToken(secret)
    return client


def write_case(
    *,
    case_id: str,
    customer_id: str = "",
    card_id: str = "",
    outcome: str = "",
    pattern: str = "",
    opened_at: str = "",
    closed_at: str = "",
    first_fraud_txn_id: str = "",
    affected_txn_ids: Iterable[str] = (),
    exposure_usd: float = 0.0,
    actions_taken: str = "",
    report_filed: bool = False,
    analyst_notes: str = "",
    connected_card_ids: str = "",
) -> dict[str, Any]:
    """Upsert one case and its verified transaction relationships."""
    client = _client()
    transaction_ids = [str(value).strip() for value in affected_txn_ids if str(value).strip()]
    attributes = {
        "customer_id": customer_id,
        "card_id": card_id,
        "outcome": outcome,
        "pattern": pattern,
        "first_fraud_txn_id": first_fraud_txn_id,
        "txn_ids": "|".join(transaction_ids),
        "n_txns": len(transaction_ids),
        "exposure_usd": float(exposure_usd),
        "connected_card_ids": connected_card_ids,
        "actions_taken": actions_taken,
        "report_filed": bool(report_filed),
        "analyst_notes": analyst_notes,
    }
    if opened_at:
        attributes["opened_at"] = opened_at
    if closed_at:
        attributes["closed_at"] = closed_at
    vertex_result = client.upsertVertex("HHGOA_ClosedCase", case_id, attributes)
    edge_count = 0
    for transaction_id in transaction_ids:
        edge_result = client.upsertEdge("HHGOA_ClosedCase", case_id, "HHGOA_INVOLVES", "HHGOA_Transaction", transaction_id, {})
        edge_count += int(edge_result or 0)
    return {
        "graph": TARGET_GRAPH,
        "case_id": case_id,
        "vertex_upserts": vertex_result,
        "involves_edge_upserts": edge_count,
        "card_edges_written": 0,
        "reason_card_edges_skipped": "No verified mapping from case card_id to prepared Card.card_id.",
    }
