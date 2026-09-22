"""Prepare HHGOA_IEEE TigerGraph CSVs without loading transactions into memory.

This prepares normalized files for a new HHGOA_IEEE graph. It never writes to
TigerGraph and never creates merchant identifiers or unsupported relationships.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

CARD_FIELDS = ["card1", "card2", "card3", "card4", "card5", "card6"]
IDENTITY_FIELDS = ["DeviceInfo", "DeviceType"] + [f"id_{i:02d}" for i in range(30, 39)]
VESTA_FIELDS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13", "C14"]
VESTA_FIELDS += [f"D{i}" for i in range(1, 16)]
VESTA_FIELDS += [f"M{i}" for i in range(1, 10)]
VESTA_FIELDS += ["V1", "V2", "V3", "V4", "V5", "V10", "V11", "V12", "V13", "V279", "V280", "V285", "V307", "V310"]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def card_key(row: dict[str, str]) -> str:
    """Return a stable key made only from the row's observed card fields."""
    values = [clean(row.get(field)) for field in CARD_FIELDS]
    if not any(values):
        return ""
    return "card:" + hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:32]


def device_key(row: dict[str, str]) -> str:
    values = [clean(row.get(field)) for field in IDENTITY_FIELDS]
    if not any(values):
        return ""
    return "device:" + hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:32]


def region_key(row: dict[str, str]) -> str:
    addr1, addr2 = clean(row.get("addr1")), clean(row.get("addr2"))
    if not addr1 and not addr2:
        return ""
    return f"region:{addr1}|{addr2}"


def domain_key(value: object) -> str:
    value = clean(value).lower()
    return "" if not value else f"domain:{value}"


def write_rows(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: clean(value) for key, value in row.items()})
            count += 1
    return count


def append_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def load_identity(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            clean(row.get("TransactionID")): row
            for row in csv.DictReader(handle)
            if clean(row.get("TransactionID"))
        }


def prepare(data_dir: Path, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "transactions.csv",
        "customers.csv",
        "cards.csv",
        "devices.csv",
        "email_domains.csv",
        "billing_regions.csv",
        "closed_cases.csv",
        "case_pack.csv",
        "made.csv",
        "from_device.csv",
        "purchaser_email.csv",
        "billed_in.csv",
        "owns.csv",
        "case_involves.csv",
        "manifest.json",
    ):
        (output_dir / filename).unlink(missing_ok=True)

    identity = load_identity(data_dir / "identity.csv")
    seen_customers: set[str] = set()
    seen_cards: dict[str, dict[str, str]] = {}
    seen_owns: set[tuple[str, str]] = set()
    seen_devices: dict[str, dict[str, str]] = {}
    seen_domains: set[str] = set()
    seen_regions: dict[str, dict[str, str]] = {}
    counts = {"transactions": 0, "customers": 0, "cards": 0, "devices": 0, "domains": 0, "regions": 0, "case_involves": 0}

    tx_fields = ["TransactionID", "TransactionDT", "TransactionAmt", "customer_id", "ts", "channel", "risk_score", "ProductCD"]
    tx_fields += CARD_FIELDS + ["addr1", "addr2", "dist1", "dist2", "P_emaildomain", "R_emaildomain"] + VESTA_FIELDS
    tx_rows = []
    edge_buffers = {
        "made.csv": (['card_id', 'TransactionID'], []),
        "from_device.csv": (['TransactionID', 'device_profile_id'], []),
        "purchaser_email.csv": (['TransactionID', 'domain'], []),
        "billed_in.csv": (['TransactionID', 'region_id'], []),
        "owns.csv": (['customer_id', 'card_id'], []),
    }

    with (data_dir / "transactions.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            tx_id = clean(row.get("TransactionID"))
            if not tx_id:
                continue
            customer_id = clean(row.get("customer_id"))
            key = card_key(row)
            identity_row = identity.get(tx_id, {})
            dkey = device_key(identity_row)
            rkey = region_key(row)
            tx_rows.append({field: row.get(field, "") for field in tx_fields})
            if customer_id:
                seen_customers.add(customer_id)
            if key:
                seen_cards.setdefault(key, {"card_id": key, "customer_id": customer_id, **{field: clean(row.get(field)) for field in CARD_FIELDS}})
                edge_buffers["made.csv"][1].append({"card_id": key, "TransactionID": tx_id})
                if customer_id:
                    ownership = (customer_id, key)
                    if ownership not in seen_owns:
                        seen_owns.add(ownership)
                        edge_buffers["owns.csv"][1].append({"customer_id": customer_id, "card_id": key})
            if dkey:
                seen_devices.setdefault(dkey, {"device_profile_id": dkey, **{field: clean(identity_row.get(field)) for field in IDENTITY_FIELDS}})
                edge_buffers["from_device.csv"][1].append({"TransactionID": tx_id, "device_profile_id": dkey})
            for field in ("P_emaildomain", "R_emaildomain"):
                domain = domain_key(row.get(field))
                if domain:
                    seen_domains.add(domain)
                    edge_buffers["purchaser_email.csv"][1].append({"TransactionID": tx_id, "domain": domain})
            if rkey:
                seen_regions.setdefault(rkey, {"region_id": rkey, "addr1": clean(row.get("addr1")), "addr2": clean(row.get("addr2"))})
                edge_buffers["billed_in.csv"][1].append({"TransactionID": tx_id, "region_id": rkey})
            counts["transactions"] += 1
            if len(tx_rows) >= 10000:
                append_rows(output_dir / "transactions.csv", tx_fields, tx_rows)
                tx_rows.clear()
            for filename, (fields, rows) in edge_buffers.items():
                if len(rows) >= 10000:
                    append_rows(output_dir / filename, fields, rows)
                    rows.clear()
    if tx_rows:
        append_rows(output_dir / "transactions.csv", tx_fields, tx_rows)
    for filename, (fields, rows) in edge_buffers.items():
        append_rows(output_dir / filename, fields, rows)

    counts["customers"] = write_rows(output_dir / "customers.csv", ["customer_id"], ({"customer_id": value} for value in sorted(seen_customers)))
    counts["cards"] = write_rows(output_dir / "cards.csv", ["card_id", "customer_id"] + CARD_FIELDS, seen_cards.values())
    counts["devices"] = write_rows(output_dir / "devices.csv", ["device_profile_id"] + IDENTITY_FIELDS, seen_devices.values())
    counts["domains"] = write_rows(output_dir / "email_domains.csv", ["domain"], ({"domain": value} for value in sorted(seen_domains)))
    counts["regions"] = write_rows(output_dir / "billing_regions.csv", ["region_id", "addr1", "addr2"], seen_regions.values())
    with (data_dir / "closed_cases_history.csv").open(newline="", encoding="utf-8") as handle:
        case_fields = ["case_id", "customer_id", "card_id", "opened_at", "closed_at", "outcome", "pattern", "first_fraud_txn_id", "txn_ids", "n_txns", "exposure_usd", "connected_card_ids", "actions_taken", "report_filed", "analyst_notes"]
        case_reader = csv.DictReader(handle)
        cases = []
        for case in case_reader:
            case["report_filed"] = "true" if clean(case.get("report_filed")).lower() in {"yes", "true", "1"} else "false"
            cases.append(case)
        counts["closed_cases"] = write_rows(output_dir / "closed_cases.csv", case_fields, cases)
    case_edges = []
    with (data_dir / "closed_cases_history.csv").open(newline="", encoding="utf-8") as handle:
        for case in csv.DictReader(handle):
            for transaction_id in clean(case.get("txn_ids")).split("|"):
                if transaction_id:
                    case_edges.append({"case_id": clean(case.get("case_id")), "TransactionID": transaction_id})
    counts["case_involves"] = write_rows(output_dir / "case_involves.csv", ["case_id", "TransactionID"], case_edges)

    with (data_dir / "case_pack.csv").open(newline="", encoding="utf-8") as handle:
        case_reader = csv.DictReader(handle)
        counts["case_pack"] = write_rows(
            output_dir / "case_pack.csv",
            list(case_reader.fieldnames or []),
            case_reader,
        )
    (output_dir / "manifest.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/hhgoa_ieee_load"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.data_dir, args.output_dir), indent=2))
