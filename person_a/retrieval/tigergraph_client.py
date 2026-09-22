import os
import hashlib
import pyTigerGraph as tg
from dotenv import load_dotenv

load_dotenv()


class TigerGraphFraudClient:

    def __init__(self):
        self.host = os.getenv("TG_HOST")
        self.secret = os.getenv("TG_SECRET")
        # HHGOA_GRAPH is separate from the legacy TG_GRAPH setting so the
        # reference graph cannot be selected accidentally for this project.
        self.graph = os.getenv("HHGOA_GRAPH", "HHGOA_IEEE")

        if not self.host:
            raise ValueError("TG_HOST is missing from .env")

        if not self.secret:
            raise ValueError("TG_SECRET is missing from .env")

        self.conn = tg.TigerGraphConnection(
            host=self.host,
            graphname=self.graph,
            gsqlSecret=self.secret,
        )

        # Authenticate using the Cloud database secret
        self.conn.getToken(self.secret)

    # -----------------------------------------
    # HHGOA_IEEE INVESTIGATION QUERIES
    # -----------------------------------------

    def get_transaction(self, transaction_id: str):
        return self.conn.runInstalledQuery("transaction_profile", {"transaction_id": str(transaction_id)})

    def get_customer_history(self, customer_id: str):
        return self.conn.runInstalledQuery("customer_history", {"customer_id": str(customer_id)})

    def get_card_history(self, card_id: str):
        return self.conn.runInstalledQuery("card_history", {"card_id": str(card_id)})

    def get_related_transactions(self, card_id: str):
        return self.conn.runInstalledQuery("related_transactions", {"card_id": str(card_id)})

    def get_region_neighbors(self, region_id: str):
        return self.conn.runInstalledQuery("region_neighbors", {"region_id": str(region_id)})

    def get_email_domain_neighbors(self, domain: str):
        return self.conn.runInstalledQuery("email_domain_neighbors", {"domain": str(domain)})

    def get_similar_closed_cases(self, customer_id: str, pattern: str = ""):
        return self.conn.runInstalledQuery(
            "similar_closed_cases",
            {"customer_id": str(customer_id), "pattern": str(pattern)},
        )

    def get_case(self, case_id: str):
        return self.conn.runInstalledQuery("get_case", {"case_id": str(case_id)})

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

    def get_transaction_network(self, transaction_id: str, cutoff_time: str):
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