import os
import hashlib
try:
    import pyTigerGraph as tg
except ImportError:
    tg = None
from dotenv import load_dotenv

load_dotenv()


class TigerGraphFraudClient:

    def __init__(self, graph: str | None = None):
        self.host = os.getenv("TG_HOST")
        self.secret = os.getenv("TG_SECRET")
        # HHGOA_GRAPH is separate from the legacy TG_GRAPH setting so the
        # reference graph cannot be selected accidentally for this project.
        self.graph = graph or os.getenv("HHGOA_GRAPH", "HHGOA_IEEE")
        self.conn = None
        self._card_info: dict[str, tuple[Any, Any]] = {}

        if self.host and self.secret and tg is not None:
            try:
                self.conn = tg.TigerGraphConnection(
                    host=self.host,
                    graphname=self.graph,
                    gsqlSecret=self.secret,
                )
                self.conn.getToken(self.secret)
            except Exception:
                self.conn = None

    # -----------------------------------------
    # HHGOA_IEEE / Transaction_Fraud INVESTIGATION QUERIES
    # -----------------------------------------

    def get_transaction(self, transaction_id: str):
        if self.conn:
            query_name = "fraud_transaction_profile" if self.graph == "Transaction_Fraud" else "transaction_profile"
            return self.conn.runInstalledQuery(query_name, {"transaction_id": str(transaction_id)})
        from tools.data_store import DataStore
        tx = DataStore.get_instance().get_transaction(str(transaction_id).strip())
        if not tx or not tx.get("found", True):
            return []
        cd = tx.get("card_details", {})
        raw_attrs = tx.get("attributes", {})
        attrs = {
            "TransactionID": str(tx.get("transaction_id", transaction_id)),
            "customer_id": tx.get("customer_id"),
            "TransactionAmt": tx.get("amount"),
            "amount": tx.get("amount"),
            "channel": tx.get("channel"),
            "addr1": tx.get("billing_region") or raw_attrs.get("addr1"),
            "risk_score": tx.get("risk_score"),
            "ts": tx.get("timestamp"),
            "card1": cd.get("card1"),
            "card2": cd.get("card2"),
            "card3": cd.get("card3"),
            "card4": cd.get("card4"),
            "card5": cd.get("card5"),
            "card6": cd.get("card6"),
            "P_emaildomain": raw_attrs.get("P_emaildomain"),
            "R_emaildomain": raw_attrs.get("R_emaildomain"),
            "cnt_repeated_card": 0,
            "max_txn_amt_interval": 0,
            "max_txn_cnt_interval": 0,
            "com_mer_txn_cnt": 0,
        }
        cid_hash = self.card_id_from_attributes(attrs)
        if cid_hash:
            self._card_info[cid_hash] = (attrs.get("card1"), attrs.get("customer_id"))
        return [{"result": [{"v_id": str(transaction_id), "attributes": attrs}]}]

    def get_customer_history(self, customer_id: str):
        if self.conn:
            return self.conn.runInstalledQuery("customer_history", {"customer_id": str(customer_id)})
        from tools.data_store import DataStore
        hist = DataStore.get_instance().get_customer_history(str(customer_id).strip())
        txns = [{"v_id": str(t.get("TransactionID", "")), "attributes": t} for t in hist.get("transactions", [])]
        cards = [{"v_id": str(c), "attributes": {"card_id": str(c)}} for c in hist.get("cards", [])]
        return [{"cards": cards, "txns": txns}]

    def get_card_history(self, card_id: str):
        if self.conn:
            return self.conn.runInstalledQuery("card_history", {"card_id": str(card_id)})
        from tools.data_store import DataStore
        hist = DataStore.get_instance().get_card_history(str(card_id).strip())
        txns = [{"v_id": str(t.get("TransactionID", "")), "attributes": t} for t in hist.get("transactions", [])]
        return [{"card": [{"v_id": str(card_id)}], "txns": txns}]

    def get_related_transactions(self, card_id: str):
        if self.conn:
            return self.conn.runInstalledQuery("related_transactions", {"card_id": str(card_id)})
        from tools.data_store import DataStore
        if card_id in self._card_info:
            c1, cust = self._card_info[card_id]
            txns = DataStore.get_instance().query(
                "SELECT * FROM transactions WHERE card1 = ? AND customer_id = ? ORDER BY ts ASC LIMIT 50",
                [c1, cust],
            )
        elif "-K" in card_id:
            cid = card_id.split("-K")[0]
            txns = DataStore.get_instance().query(
                "SELECT * FROM transactions WHERE customer_id = ? ORDER BY ts ASC LIMIT 50",
                [cid],
            )
        else:
            txns = DataStore.get_instance().query(
                "SELECT * FROM transactions WHERE customer_id = ? ORDER BY ts ASC LIMIT 50",
                [card_id],
            )
        formatted = [{"v_id": str(t["TransactionID"]), "attributes": {
            "TransactionID": str(t["TransactionID"]),
            "amount": t.get("TransactionAmt"),
            "TransactionAmt": t.get("TransactionAmt"),
            "transaction_time": str(t.get("ts", "")),
        }} for t in txns]
        return [{"txns": formatted}]

    def get_region_neighbors(self, region_id: str):
        if self.conn:
            return self.conn.runInstalledQuery("region_neighbors", {"region_id": str(region_id)})
        return [{"region": [{"v_id": str(region_id)}]}]

    def get_email_domain_neighbors(self, domain: str):
        if self.conn:
            return self.conn.runInstalledQuery("email_domain_neighbors", {"domain": str(domain)})
        return [{"domain": [{"v_id": str(domain)}]}]

    def get_similar_closed_cases(self, customer_id: str, pattern: str = ""):
        if self.conn:
            return self.conn.runInstalledQuery(
                "similar_closed_cases",
                {"customer_id": str(customer_id), "pattern": str(pattern)},
            )
        from tools.data_store import DataStore
        cases = DataStore.get_instance().get_similar_closed_cases(customer_id=str(customer_id).strip(), pattern=str(pattern).strip())
        results = []
        for c in cases.get("cases", cases.get("similar_cases", [])):
            results.append({
                "v_id": str(c.get("case_id", "")),
                "attributes": {
                    "case_id": str(c.get("case_id", "")),
                    "customer_id": c.get("customer_id"),
                    "outcome": c.get("outcome", c.get("verdict")),
                    "similarity": c.get("similarity"),
                },
            })
        return [{"cases": results}]

    def get_case(self, case_id: str):
        if self.conn:
            return self.conn.runInstalledQuery("get_case", {"case_id": str(case_id)})
        from tools.data_store import DataStore
        c = DataStore.get_instance().get_closed_case(str(case_id).strip())
        if not c or not c.get("found", True):
            return []
        return [{"result": [{"v_id": str(case_id), "attributes": c.get("case_record", {})}]}]

    @staticmethod
    def card_id_from_attributes(attributes: dict) -> str:
        values = [str(attributes.get(field, "") or "").strip() for field in (
            "card1", "card2", "card3", "card4", "card5", "card6"
        )]
        if not any(values):
            return ""
        return "card:" + hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def region_id_from_attributes(attributes: dict) -> str:
        addr1 = str(attributes.get("addr1", "") or "").strip()
        addr2 = str(attributes.get("addr2", "") or "").strip()
        return f"region:{addr1}|{addr2}" if addr1 or addr2 else ""

    # -----------------------------------------
    # Compatibility wrapper for callers of the old client method.
    # -----------------------------------------

    def get_transaction_network(self, transaction_id: str, cutoff_time: str = ""):
        if self.graph == "Transaction_Fraud" and self.conn:
            return self.conn.runInstalledQuery(
                "transaction_network_evidence",
                {"transaction_id": str(transaction_id), "cutoff_time": str(cutoff_time)},
            )
        profile = self.get_transaction(transaction_id)
        if not profile or not profile[0].get("result"):
            return []
        attrs = profile[0]["result"][0].get("attributes", {})
        card_id = self.card_id_from_attributes(attrs)
        return self.get_related_transactions(card_id) if card_id else []

if __name__ == "__main__":

    client = TigerGraphFraudClient()

    result = client.get_transaction("9998")

    print("TigerGraph response:")
    print(result)