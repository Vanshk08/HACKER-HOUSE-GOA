import os
import pyTigerGraph as tg
from dotenv import load_dotenv

load_dotenv()


class TigerGraphFraudClient:

    def __init__(self):
        self.host = os.getenv("TG_HOST")
        self.secret = os.getenv("TG_SECRET")
        self.graph = os.getenv("TG_GRAPH", "Transaction_Fraud")

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
    # BASIC TRANSACTION PROFILE
    # -----------------------------------------

    def get_transaction(self, transaction_id: str):
        return self.conn.runInstalledQuery(
            "fraud_transaction_profile",
            params={
                "transaction_id": transaction_id
            },
        )

    # -----------------------------------------
    # CARD + RELATED TRANSACTION NETWORK
    # -----------------------------------------

    def get_transaction_network(self, transaction_id: str, cutoff_time: str):
        return self.conn.runInstalledQuery(
            "transaction_network_evidence",
            params={
                "transaction_id": transaction_id,
                "cutoff_time": cutoff_time,
            },
        )

if __name__ == "__main__":

    client = TigerGraphFraudClient()

    result = client.get_transaction("9998")

    print("TigerGraph response:")
    print(result)