"""
Local analytical data access layer over the challenge datasets using DuckDB.
Queries data/fraud_data.duckdb or the raw CSVs efficiently without loading
full datasets into memory.
"""

import os
import duckdb
from typing import Any, Optional
from datetime import datetime


def _resolve_dataset_path(data_dir: str, filename: str) -> str:
    """Return the canonical path for challenge CSV files, including the data/raw layout."""
    candidates = [
        os.path.join(data_dir, filename),
        os.path.join(data_dir, "raw", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def _get_data_dir() -> str:
    # Look for data directory relative to project root
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base, "data")
    if os.path.exists(data_dir):
        return data_dir
    # Fallback to current working directory or known location
    fallback = r"D:\tiger graph hhg\fraud-agent\data"
    if os.path.exists(fallback):
        return fallback
    return "data"


class DataStore:
    _instance: Optional["DataStore"] = None

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or _get_data_dir()
        self.db_path = os.path.join(self.data_dir, "fraud_data.duckdb").replace("\\", "/")
        self._con = None
        self._init_connection()

    @classmethod
    def get_instance(cls) -> "DataStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_connection(self):
        # Open in read-only mode if exists to allow concurrent tool usage
        if os.path.exists(self.db_path):
            try:
                self._con = duckdb.connect(self.db_path, read_only=True)
                return
            except Exception:
                pass
        
        # If not read-only or not existing, create or connect read-write to initialize
        self._con = duckdb.connect(self.db_path)
        self._ensure_tables()

    def _ensure_tables(self):
        tables = [r[0] for r in self._con.execute("SHOW TABLES").fetchall()]
        cp_path = _resolve_dataset_path(self.data_dir, "case_pack.csv").replace("\\", "/")
        cc_path = _resolve_dataset_path(self.data_dir, "closed_cases_history.csv").replace("\\", "/")
        id_path = _resolve_dataset_path(self.data_dir, "identity.csv").replace("\\", "/")
        tx_path = _resolve_dataset_path(self.data_dir, "transactions.csv").replace("\\", "/")

        if "case_pack" not in tables and os.path.exists(cp_path):
            self._con.execute(f"CREATE TABLE case_pack AS SELECT * FROM read_csv_auto('{cp_path}')")
        if "closed_cases" not in tables and os.path.exists(cc_path):
            self._con.execute(f"CREATE TABLE closed_cases AS SELECT * FROM read_csv_auto('{cc_path}')")
        if "identity" not in tables and os.path.exists(id_path):
            self._con.execute(f"CREATE TABLE identity AS SELECT * FROM read_csv_auto('{id_path}')")
            self._con.execute("CREATE INDEX IF NOT EXISTS idx_id_tx ON identity (TransactionID)")
        if "transactions" not in tables and os.path.exists(tx_path):
            self._con.execute(f"CREATE TABLE transactions AS SELECT * FROM read_csv_auto('{tx_path}')")
            self._con.execute("CREATE INDEX IF NOT EXISTS idx_tx_id ON transactions (TransactionID)")
            self._con.execute("CREATE INDEX IF NOT EXISTS idx_tx_cust ON transactions (customer_id)")
            self._con.execute("CREATE INDEX IF NOT EXISTS idx_tx_addr1 ON transactions (addr1)")

    def query(self, sql: str, params: Optional[list] = None) -> list[dict[str, Any]]:
        cursor = self._con.cursor()
        if params:
            df = cursor.execute(sql, params).df()
        else:
            df = cursor.execute(sql).df()
        # Clean up NaNs / types for JSON compatibility
        records = []
        for row in df.to_dict(orient="records"):
            clean_row = {}
            for k, v in row.items():
                if v is None or (isinstance(v, float) and v != v):
                    clean_row[k] = None
                elif isinstance(v, (datetime,)):
                    clean_row[k] = v.isoformat()
                else:
                    clean_row[k] = v
            records.append(clean_row)
        return records

    def get_transaction(self, transaction_id: str) -> Optional[dict[str, Any]]:
        try:
            tx_id_int = int(transaction_id)
        except (ValueError, TypeError):
            return None

        records = self.query(
            "SELECT * FROM transactions WHERE TransactionID = ?",
            [tx_id_int]
        )
        if not records:
            return None

        row = records[0]
        # Query identity record if available
        id_records = self.query(
            "SELECT * FROM identity WHERE TransactionID = ?",
            [tx_id_int]
        )
        identity_info = id_records[0] if id_records else None

        # Build clean attributes
        c_counts = {f"C{i}": row.get(f"C{i}") for i in range(1, 15) if row.get(f"C{i}") is not None}
        d_timedeltas = {f"D{i}": row.get(f"D{i}") for i in range(1, 16) if row.get(f"D{i}") is not None}
        m_matches = {f"M{i}": row.get(f"M{i}") for i in range(1, 10) if row.get(f"M{i}") is not None}
        v_features = {f"V{i}": row.get(f"V{i}") for i in [1, 2, 3, 4, 5, 10, 11, 12, 13, 279, 280, 285, 307, 310] if row.get(f"V{i}") is not None}

        # Resolve card_id from case_pack or closed_cases if available
        customer_id = row.get("customer_id")
        card_id = None
        if customer_id:
            cp = self.query("SELECT card_id FROM case_pack WHERE customer_id = ? LIMIT 1", [customer_id])
            if cp and cp[0].get("card_id"):
                card_id = cp[0]["card_id"]
            else:
                cc = self.query("SELECT card_id FROM closed_cases WHERE customer_id = ? LIMIT 1", [customer_id])
                if cc and cc[0].get("card_id"):
                    card_id = cc[0]["card_id"]
                else:
                    card_id = f"{customer_id}-K1"

        return {
            "transaction_id": str(row["TransactionID"]),
            "customer_id": str(customer_id) if customer_id else None,
            "card_id": str(card_id) if card_id else None,
            "timestamp": str(row.get("ts")),
            "amount": float(row.get("TransactionAmt")) if row.get("TransactionAmt") is not None else None,
            "channel": str(row.get("channel")),
            "billing_region": str(int(row["addr1"])) if row.get("addr1") is not None else None,
            "risk_score": float(row.get("risk_score")) if row.get("risk_score") is not None else None,
            "card_details": {
                "card1": row.get("card1"),
                "card2": row.get("card2"),
                "card3": row.get("card3"),
                "card4": row.get("card4"),
                "card5": row.get("card5"),
                "card6": row.get("card6"),
            },
            "attributes": {
                "addr1": row.get("addr1"),
                "addr2": row.get("addr2"),
                "dist1": row.get("dist1"),
                "dist2": row.get("dist2"),
                "P_emaildomain": row.get("P_emaildomain"),
                "R_emaildomain": row.get("R_emaildomain"),
                "C_counts": c_counts,
                "D_timedeltas": d_timedeltas,
                "M_matches": m_matches,
                "V_features": v_features,
            },
            "identity": {
                "DeviceType": identity_info.get("DeviceType") if identity_info else None,
                "DeviceInfo": identity_info.get("DeviceInfo") if identity_info else None,
                "id_30_OS": identity_info.get("id_30") if identity_info else None,
                "id_31_Browser": identity_info.get("id_31") if identity_info else None,
            } if identity_info else None,
            "backend_status": "real_dataset",
        }

    def get_transaction_sequence(
        self,
        customer_id: str,
        transaction_id: str,
        window_minutes: int = 60,
    ) -> dict[str, Any]:
        target = self.get_transaction(transaction_id)
        if not target or not target.get("timestamp"):
            return {
                "customer_id": customer_id,
                "target_transaction_id": transaction_id,
                "window_minutes": window_minutes,
                "target_transaction": None,
                "previous_transactions": [],
                "subsequent_transactions": [],
                "backend_status": "real_dataset",
                "backend_note": "Target transaction not found.",
            }

        target_ts = target["timestamp"]
        # Fetch transactions within time window
        window_sec = window_minutes * 60
        txs = self.query(f"""
            SELECT TransactionID, customer_id, ts, TransactionAmt, channel, addr1, risk_score,
                   epoch(CAST(ts AS TIMESTAMP)) as epoch_sec
            FROM transactions
            WHERE customer_id = ?
              AND epoch(CAST(ts AS TIMESTAMP)) BETWEEN (epoch(CAST(? AS TIMESTAMP)) - {window_sec})
                                                   AND (epoch(CAST(? AS TIMESTAMP)) + {window_sec})
            ORDER BY ts ASC
        """, [customer_id, target_ts, target_ts])

        target_epoch = None
        for t in txs:
            if str(t["TransactionID"]) == str(transaction_id):
                target_epoch = t["epoch_sec"]
                break

        prev_txs = []
        sub_txs = []
        time_diffs = []
        regions = set()

        for t in txs:
            t_id = str(t["TransactionID"])
            item = {
                "transaction_id": t_id,
                "timestamp": str(t["ts"]),
                "amount": float(t["TransactionAmt"]) if t.get("TransactionAmt") is not None else None,
                "channel": t.get("channel"),
                "region": str(int(t["addr1"])) if t.get("addr1") is not None else None,
                "risk_score": float(t["risk_score"]) if t.get("risk_score") is not None else None,
            }
            if item["region"]:
                regions.add(item["region"])

            if target_epoch is not None and t["epoch_sec"] is not None:
                delta = t["epoch_sec"] - target_epoch
                if delta < 0:
                    prev_txs.append(item)
                    time_diffs.append(abs(delta))
                elif delta > 0:
                    sub_txs.append(item)
                    time_diffs.append(delta)

        return {
            "customer_id": customer_id,
            "target_transaction_id": transaction_id,
            "window_minutes": window_minutes,
            "target_transaction": target,
            "previous_transactions": prev_txs,
            "subsequent_transactions": sub_txs,
            "time_differences": time_diffs,
            "derived_calculations": {
                "total_transactions_in_window": len(txs),
                "velocity_transactions_per_hour": round((len(txs) / max(1, window_minutes)) * 60, 2),
                "distinct_regions_observed": sorted(list(regions)),
                "rapid_sequence_detected": any(d < 120 for d in time_diffs) if time_diffs else False,
            },
            "backend_status": "real_dataset",
        }

    def get_customer_history(self, customer_id: str) -> dict[str, Any]:
        stats = self.query("""
            SELECT 
                COUNT(*) as total_txns,
                MIN(ts) as first_seen,
                MAX(ts) as last_seen,
                ROUND(AVG(TransactionAmt), 2) as avg_amt,
                ROUND(MEDIAN(TransactionAmt), 2) as median_amt,
                ROUND(MIN(TransactionAmt), 2) as min_amt,
                ROUND(MAX(TransactionAmt), 2) as max_amt,
                ROUND(STDDEV(TransactionAmt), 2) as std_amt
            FROM transactions 
            WHERE customer_id = ?
        """, [customer_id])

        if not stats or stats[0]["total_txns"] == 0:
            return {
                "customer_id": customer_id,
                "total_transactions": 0,
                "backend_status": "real_dataset",
                "backend_note": "Customer not found in transactions dataset.",
            }

        st = stats[0]
        # Get regions
        regions = self.query("""
            SELECT CAST(addr1 AS VARCHAR) as region, COUNT(*) as cnt
            FROM transactions WHERE customer_id = ? AND addr1 IS NOT NULL
            GROUP BY addr1 ORDER BY cnt DESC LIMIT 10
        """, [customer_id])

        # Get channels
        channels = self.query("""
            SELECT channel, COUNT(*) as cnt
            FROM transactions WHERE customer_id = ? AND channel IS NOT NULL
            GROUP BY channel ORDER BY cnt DESC
        """, [customer_id])

        # Get recent transactions
        recent = self.query("""
            SELECT TransactionID, ts, TransactionAmt, channel, addr1, risk_score
            FROM transactions WHERE customer_id = ?
            ORDER BY ts DESC LIMIT 8
        """, [customer_id])

        recent_clean = [
            {
                "transaction_id": str(r["TransactionID"]),
                "timestamp": str(r["ts"]),
                "amount": float(r["TransactionAmt"]) if r.get("TransactionAmt") is not None else None,
                "channel": r.get("channel"),
                "billing_region": str(int(r["addr1"])) if r.get("addr1") is not None else None,
                "risk_score": float(r["risk_score"]) if r.get("risk_score") is not None else None,
            }
            for r in recent
        ]

        return {
            "customer_id": customer_id,
            "first_seen": str(st["first_seen"]),
            "last_seen": str(st["last_seen"]),
            "total_transactions": int(st["total_txns"]),
            "historical_regions": [str(int(float(r["region"]))) for r in regions if r.get("region")],
            "historical_channels": [r["channel"] for r in channels if r.get("channel")],
            "recent_transactions": recent_clean,
            "derived_calculations": {
                "normal_spending_behavior": {
                    "mean_amount": st["avg_amt"],
                    "median_amount": st["median_amt"],
                    "min_amount": st["min_amt"],
                    "max_amount": st["max_amt"],
                    "std_dev_amount": st["std_amt"],
                },
                "frequent_channels": [r["channel"] for r in channels[:3]],
                "frequent_regions": [str(int(float(r["region"]))) for r in regions[:5] if r.get("region")],
            },
            "backend_status": "real_dataset",
        }

    def get_customer_cards(self, customer_id: str) -> dict[str, Any]:
        cards_res = self.query("""
            SELECT card1, card2, card3, card4, card5, card6,
                   COUNT(*) as txn_count,
                   MIN(ts) as first_used,
                   MAX(ts) as last_used
            FROM transactions
            WHERE customer_id = ?
            GROUP BY card1, card2, card3, card4, card5, card6
            ORDER BY txn_count DESC
        """, [customer_id])

        # Look for explicit card_id
        known_card_id = None
        cp = self.query("SELECT card_id FROM case_pack WHERE customer_id = ? LIMIT 1", [customer_id])
        if cp and cp[0].get("card_id"):
            known_card_id = cp[0]["card_id"]

        cards = []
        card_ids = []
        for idx, c in enumerate(cards_res):
            cid = known_card_id if (idx == 0 and known_card_id) else f"{customer_id}-K{idx+1}"
            card_ids.append(cid)
            cards.append({
                "card_id": cid,
                "card1": c.get("card1"),
                "card2": c.get("card2"),
                "card3": c.get("card3"),
                "brand": c.get("card4"),
                "card_type": c.get("card6"),
                "transaction_count": int(c["txn_count"]),
                "first_used": str(c["first_used"]),
                "last_used": str(c["last_used"]),
            })

        return {
            "customer_id": customer_id,
            "card_ids": card_ids,
            "cards": cards,
            "derived_calculations": {
                "total_cards_count": len(cards),
                "primary_card_id": card_ids[0] if card_ids else None,
            },
            "backend_status": "real_dataset",
        }

    def get_card_history(self, card_id: str) -> dict[str, Any]:
        # Extract customer_id if card_id has standard prefix, e.g. C12382-K1
        customer_id = card_id.split("-")[0] if "-" in card_id else card_id
        
        # Verify customer in transactions
        txs = self.query("""
            SELECT COUNT(*) as total_txns,
                   ROUND(SUM(TransactionAmt), 2) as total_volume,
                   MIN(ts) as first_obs,
                   MAX(ts) as last_obs,
                   ROUND(AVG(TransactionAmt), 2) as avg_amt,
                   ROUND(MEDIAN(TransactionAmt), 2) as median_amt,
                   ROUND(MIN(TransactionAmt), 2) as min_amt,
                   ROUND(MAX(TransactionAmt), 2) as max_amt
            FROM transactions
            WHERE customer_id = ?
        """, [customer_id])

        st = txs[0] if txs else {}

        # Query regions
        regions = self.query("""
            SELECT DISTINCT CAST(addr1 AS VARCHAR) as region
            FROM transactions WHERE customer_id = ? AND addr1 IS NOT NULL
        """, [customer_id])

        # Query channels
        channels = self.query("""
            SELECT DISTINCT channel
            FROM transactions WHERE customer_id = ? AND channel IS NOT NULL
        """, [customer_id])

        # Query closed cases for this card / customer
        cases = self.query("""
            SELECT case_id, customer_id, card_id, outcome, pattern, exposure_usd, opened_at, closed_at, analyst_notes
            FROM closed_cases
            WHERE card_id = ? OR customer_id = ?
        """, [card_id, customer_id])

        confirmed_cases = [c for c in cases if c.get("outcome") == "confirmed_fraud"]
        suspicious_cases = [c for c in cases if c.get("outcome") != "confirmed_fraud"]

        return {
            "card_id": card_id,
            "first_observed": str(st.get("first_obs")) if st.get("first_obs") else None,
            "last_observed": str(st.get("last_obs")) if st.get("last_obs") else None,
            "total_transactions": int(st.get("total_txns", 0)),
            "total_volume": float(st.get("total_volume", 0.0)) if st.get("total_volume") is not None else 0.0,
            "observed_regions": [str(int(float(r["region"]))) for r in regions if r.get("region")],
            "observed_channels": [r["channel"] for r in channels if r.get("channel")],
            "previous_suspicious_cases": [c["case_id"] for c in suspicious_cases],
            "previous_confirmed_cases": [c["case_id"] for c in confirmed_cases],
            "historical_cases_details": cases,
            "derived_calculations": {
                "spending_patterns": {
                    "mean_amount": st.get("avg_amt"),
                    "median_amount": st.get("median_amt"),
                    "min_amount": st.get("min_amt"),
                    "max_amount": st.get("max_amt"),
                },
                "distinct_regions_count": len(regions),
                "distinct_channels_count": len(channels),
                "has_previous_confirmed_fraud": len(confirmed_cases) > 0,
            },
            "backend_status": "real_dataset",
        }

    def get_connected_cards(self, card_id: str) -> dict[str, Any]:
        customer_id = card_id.split("-")[0] if "-" in card_id else card_id

        # Query closed cases that mention connected cards
        cc = self.query("""
            SELECT case_id, card_id, connected_card_ids, outcome
            FROM closed_cases
            WHERE card_id = ? OR connected_card_ids LIKE ?
        """, [card_id, f"%{card_id}%"])

        connected_cards = set()
        connections = []

        for c in cc:
            conn_raw = c.get("connected_card_ids")
            if conn_raw:
                for c_item in str(conn_raw).replace("|", ",").split(","):
                    c_clean = c_item.strip()
                    if c_clean and c_clean != card_id:
                        connected_cards.add(c_clean)
                        connections.append({
                            "connected_card_id": c_clean,
                            "connection_type": "closed_case_investigation_link",
                            "shared_entity_id": c.get("case_id"),
                            "shared_entity_type": "HistoricalCase",
                            "case_outcome": c.get("outcome"),
                        })

        return {
            "card_id": card_id,
            "connected_card_ids": sorted(list(connected_cards)),
            "connections": connections,
            "derived_calculations": {
                "total_connected_cards": len(connected_cards),
            },
            "backend_status": "real_dataset",
        }

    def get_device_connections(
        self,
        customer_id: Optional[str] = None,
        card_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> dict[str, Any]:
        cid = customer_id or (card_id.split("-")[0] if card_id and "-" in card_id else card_id)
        
        # Query identity records for this customer
        query_sql = """
            SELECT t.TransactionID, t.customer_id, i.DeviceType, i.DeviceInfo, i.id_30, i.id_31
            FROM transactions t
            JOIN identity i ON t.TransactionID = i.TransactionID
            WHERE 1=1
        """
        params = []
        if cid:
            query_sql += " AND t.customer_id = ?"
            params.append(cid)
        if device_id:
            query_sql += " AND (i.DeviceInfo = ? OR i.DeviceType = ?)"
            params.append(device_id)
            params.append(device_id)
        
        query_sql += " LIMIT 20"
        records = self.query(query_sql, params)

        devices = set()
        customers = set()
        for r in records:
            if r.get("DeviceInfo"):
                devices.add(r["DeviceInfo"])
            if r.get("customer_id"):
                customers.add(r["customer_id"])

        return {
            "device_id": device_id,
            "query_params": {"customer_id": customer_id, "card_id": card_id, "device_id": device_id},
            "associated_customers": sorted(list(customers)),
            "associated_transactions": [str(r["TransactionID"]) for r in records],
            "observed_devices": sorted(list(devices)),
            "derived_calculations": {
                "is_shared_across_multiple_accounts": len(customers) > 1,
                "associated_customer_count": len(customers),
                "associated_transaction_count": len(records),
            },
            "backend_status": "real_dataset",
        }

    def get_customer_device_history(self, customer_id: str) -> dict[str, Any]:
        records = self.query("""
            SELECT t.TransactionID, t.ts, i.DeviceType, i.DeviceInfo, i.id_30, i.id_31
            FROM transactions t
            JOIN identity i ON t.TransactionID = i.TransactionID
            WHERE t.customer_id = ?
            ORDER BY t.ts ASC
        """, [customer_id])

        dev_map: dict[str, dict[str, Any]] = {}
        for r in records:
            d_name = r.get("DeviceInfo") or r.get("DeviceType") or "unknown_device"
            if d_name not in dev_map:
                dev_map[d_name] = {
                    "device_id": d_name,
                    "device_type": r.get("DeviceType"),
                    "device_info": r.get("DeviceInfo"),
                    "os": r.get("id_30"),
                    "browser": r.get("id_31"),
                    "transaction_count": 0,
                    "first_seen": str(r["ts"]),
                    "last_seen": str(r["ts"]),
                }
            dev_map[d_name]["transaction_count"] += 1
            dev_map[d_name]["last_seen"] = str(r["ts"])

        devices = list(dev_map.values())
        return {
            "customer_id": customer_id,
            "devices": devices,
            "derived_calculations": {
                "total_devices_count": len(devices),
                "primary_device_id": devices[0]["device_id"] if devices else None,
                "known_device_count": len(devices),
                "identity_records_found": len(records),
            },
            "backend_status": "real_dataset",
        }

    def get_region_activity(self, customer_id: str, region: str) -> dict[str, Any]:
        try:
            r_float = float(region)
        except (ValueError, TypeError):
            r_float = -1.0

        stats = self.query("""
            SELECT 
                COUNT(*) as txn_count,
                ROUND(SUM(TransactionAmt), 2) as total_amt,
                ROUND(AVG(TransactionAmt), 2) as mean_amt,
                MIN(ts) as first_obs,
                MAX(ts) as last_obs
            FROM transactions
            WHERE customer_id = ? AND addr1 = ?
        """, [customer_id, r_float])

        st = stats[0] if stats else {}
        cnt = int(st.get("txn_count", 0))

        # Overall customer spend to compute percentages
        total_cust = self.query("""
            SELECT COUNT(*) as total_cnt, SUM(TransactionAmt) as total_amt
            FROM transactions WHERE customer_id = ?
        """, [customer_id])
        cust_cnt = int(total_cust[0]["total_cnt"]) if total_cust and total_cust[0]["total_cnt"] else 1
        cust_amt = float(total_cust[0]["total_amt"]) if total_cust and total_cust[0]["total_amt"] else 1.0

        sample_txs = self.query("""
            SELECT TransactionID, ts, TransactionAmt, risk_score
            FROM transactions WHERE customer_id = ? AND addr1 = ?
            ORDER BY ts DESC LIMIT 10
        """, [customer_id, r_float])

        return {
            "customer_id": customer_id,
            "region": region,
            "transaction_count": cnt,
            "first_observed": str(st.get("first_obs")) if st.get("first_obs") else None,
            "most_recent_observed": str(st.get("last_obs")) if st.get("last_obs") else None,
            "transaction_ids": [str(t["TransactionID"]) for t in sample_txs],
            "derived_calculations": {
                "is_previously_observed": cnt > 0,
                "total_amount_in_region": float(st.get("total_amt", 0.0)) if st.get("total_amt") is not None else 0.0,
                "mean_amount_in_region": st.get("mean_amt"),
                "percentage_of_customer_transactions": round((cnt / max(1, cust_cnt)) * 100, 2),
                "percentage_of_customer_spend": round(((float(st.get("total_amt", 0.0)) or 0.0) / max(1.0, cust_amt)) * 100, 2),
            },
            "backend_status": "real_dataset",
        }

    def get_customer_regions(self, customer_id: str) -> dict[str, Any]:
        regions = self.query("""
            SELECT CAST(addr1 AS VARCHAR) as region_code,
                   COUNT(*) as transaction_count,
                   ROUND(SUM(TransactionAmt), 2) as total_amount,
                   MIN(ts) as first_activity,
                   MAX(ts) as last_activity
            FROM transactions
            WHERE customer_id = ? AND addr1 IS NOT NULL
            GROUP BY addr1
            ORDER BY transaction_count DESC
        """, [customer_id])

        clean_regions = []
        region_codes = []
        for r in regions:
            rcode = str(int(float(r["region_code"])))
            region_codes.append(rcode)
            clean_regions.append({
                "region_code": rcode,
                "transaction_count": int(r["transaction_count"]),
                "total_amount": float(r["total_amount"]) if r.get("total_amount") is not None else 0.0,
                "first_activity": str(r["first_activity"]),
                "last_activity": str(r["last_activity"]),
            })

        return {
            "customer_id": customer_id,
            "region_codes": region_codes,
            "regions": clean_regions,
            "derived_calculations": {
                "total_regions_count": len(clean_regions),
                "primary_region": region_codes[0] if region_codes else None,
            },
            "backend_status": "real_dataset",
        }

    def get_similar_closed_cases(
        self,
        customer_id: Optional[str] = None,
        card_id: Optional[str] = None,
        pattern: Optional[str] = None,
        region: Optional[str] = None,
    ) -> dict[str, Any]:
        sql = "SELECT * FROM closed_cases WHERE 1=1"
        params = []
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if card_id:
            sql += " AND card_id = ?"
            params.append(card_id)
        if pattern:
            sql += " AND pattern = ?"
            params.append(pattern)
        if region:
            sql += " AND analyst_notes LIKE ?"
            params.append(f"%{region}%")

        sql += " ORDER BY opened_at DESC LIMIT 10"
        records = self.query(sql, params)

        cases = [
            {
                "case_id": r["case_id"],
                "customer_id": r["customer_id"],
                "card_id": r["card_id"],
                "verdict": r["outcome"],
                "pattern": r["pattern"],
                "exposure": float(r["exposure_usd"]) if r.get("exposure_usd") is not None else 0.0,
                "opened_at": str(r["opened_at"]),
                "closed_at": str(r["closed_at"]),
                "relevant_analyst_notes": r.get("analyst_notes"),
            }
            for r in records
        ]

        verdict_counts: dict[str, int] = {}
        for c in cases:
            v = c["verdict"]
            verdict_counts[v] = verdict_counts.get(v, 0) + 1

        return {
            "query_params": {"customer_id": customer_id, "card_id": card_id, "pattern": pattern, "region": region},
            "cases": cases,
            "total_matches": len(cases),
            "derived_calculations": {
                "precedent_count": len(cases),
                "historical_verdict_breakdown": verdict_counts,
            },
            "backend_status": "real_dataset",
        }

    def get_closed_case(self, case_id: str) -> dict[str, Any]:
        records = self.query("SELECT * FROM closed_cases WHERE case_id = ?", [case_id])
        if not records:
            return {
                "case_id": case_id,
                "backend_status": "real_dataset",
                "backend_note": f"Case {case_id} not found in closed cases history.",
            }

        r = records[0]
        txns_str = r.get("txn_ids") or ""
        tx_list = [t.strip() for t in str(txns_str).split(",") if t.strip()]

        return {
            "case_id": r["case_id"],
            "customer_id": r.get("customer_id"),
            "card_id": r.get("card_id"),
            "flagged_txn_id": r.get("first_fraud_txn_id"),
            "verdict": r.get("outcome"),
            "pattern": r.get("pattern"),
            "exposure": float(r["exposure_usd"]) if r.get("exposure_usd") is not None else 0.0,
            "affected_transaction_ids": tx_list,
            "actions": [r.get("actions_taken")] if r.get("actions_taken") else [],
            "relevant_analyst_notes": r.get("analyst_notes"),
            "opened_at": str(r.get("opened_at")),
            "closed_at": str(r.get("closed_at")),
            "backend_status": "real_dataset",
        }

    def find_shared_origins(
        self,
        card_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        cid = customer_id or (card_id.split("-")[0] if card_id and "-" in card_id else card_id)
        if not cid:
            return {"shared_origins": [], "backend_status": "real_dataset"}

        # Find customer's email domain and primary region
        tx_info = self.query("""
            SELECT P_emaildomain, addr1, COUNT(*) as cnt
            FROM transactions
            WHERE customer_id = ? AND (P_emaildomain IS NOT NULL OR addr1 IS NOT NULL)
            GROUP BY P_emaildomain, addr1
            ORDER BY cnt DESC LIMIT 1
        """, [cid])

        shared_origins = []
        if tx_info:
            top = tx_info[0]
            if top.get("P_emaildomain"):
                # Count customers sharing email domain
                shared_cust = self.query("""
                    SELECT COUNT(DISTINCT customer_id) as c_cnt
                    FROM transactions WHERE P_emaildomain = ?
                """, [top["P_emaildomain"]])
                shared_origins.append({
                    "shared_entity_id": top["P_emaildomain"],
                    "entity_type": "EmailDomain",
                    "connected_customers_count": int(shared_cust[0]["c_cnt"]) if shared_cust else 1,
                })

            if top.get("addr1") is not None:
                r_code = str(int(top["addr1"]))
                shared_cust = self.query("""
                    SELECT COUNT(DISTINCT customer_id) as c_cnt
                    FROM transactions WHERE addr1 = ?
                """, [top["addr1"]])
                shared_origins.append({
                    "shared_entity_id": r_code,
                    "entity_type": "BillingRegion",
                    "connected_customers_count": int(shared_cust[0]["c_cnt"]) if shared_cust else 1,
                })

        return {
            "query_params": {"card_id": card_id, "customer_id": customer_id},
            "shared_origins": shared_origins,
            "derived_calculations": {
                "total_shared_entities": len(shared_origins),
            },
            "backend_status": "real_dataset",
        }

    def find_related_fraud(
        self,
        card_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        device_id: Optional[str] = None,
        region: Optional[str] = None,
    ) -> dict[str, Any]:
        cid = customer_id or (card_id.split("-")[0] if card_id and "-" in card_id else card_id)
        
        sql = "SELECT case_id, customer_id, card_id, pattern, outcome, exposure_usd, analyst_notes FROM closed_cases WHERE outcome = 'confirmed_fraud'"
        params = []
        if cid:
            sql += " AND (customer_id = ? OR card_id LIKE ?)"
            params.append(cid)
            params.append(f"%{cid}%")
        elif region:
            sql += " AND analyst_notes LIKE ?"
            params.append(f"%{region}%")

        sql += " LIMIT 10"
        records = self.query(sql, params)

        related = [
            {
                "case_id": r["case_id"],
                "relationship_type": "same_customer_or_card" if cid else "region_precedent",
                "connected_entity_id": cid or region,
                "historical_verdict": r["outcome"],
                "pattern": r["pattern"],
                "exposure": float(r["exposure_usd"]) if r.get("exposure_usd") is not None else 0.0,
                "details": r.get("analyst_notes"),
            }
            for r in records
        ]

        return {
            "query_params": {"card_id": card_id, "customer_id": customer_id, "device_id": device_id, "region": region},
            "related_fraud_cases": related,
            "derived_calculations": {
                "total_related_cases": len(related),
            },
            "backend_status": "real_dataset",
        }
