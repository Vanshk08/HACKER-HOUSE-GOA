from .tigergraph_client import TigerGraphFraudClient


class FraudAnalyzer:

    def __init__(self):
        self.client = TigerGraphFraudClient()

    def analyze(self, transaction_id: str):

        # -----------------------------------------
        # 1. TRANSACTION PROFILE
        # -----------------------------------------

        raw = self.client.get_transaction(transaction_id)

        if not raw or not raw[0].get("result"):
            return {
                "transaction_id": transaction_id,
                "found": False,
                "message": "Transaction not found"
            }

        transaction = raw[0]["result"][0]
        attrs = transaction["attributes"]

        score = 0
        signals = []

        amount = attrs.get("amount", 0)

        if amount > 500:
            score += 20
            signals.append(
                f"High transaction amount: {amount}"
            )

        repeated_card = attrs.get("cnt_repeated_card", 0)

        if repeated_card > 0:
            score += 20
            signals.append(
                f"Repeated card activity: {repeated_card}"
            )

        max_amount = attrs.get("max_txn_amt_interval", 0)

        if max_amount > 0:
            score += 15
            signals.append(
                f"High transaction amount within interval: {max_amount}"
            )

        max_count = attrs.get("max_txn_cnt_interval", 0)

        if max_count > 0:
            score += 15
            signals.append(
                f"High transaction count within interval: {max_count}"
            )

        merchant_count = attrs.get("com_mer_txn_cnt", 0)

        if merchant_count > 0:
            score += 10
            signals.append(
                f"Merchant community activity: {merchant_count}"
            )

        # -----------------------------------------
        # 2. GRAPH NETWORK
        # -----------------------------------------

        network_raw = self.client.get_transaction_network(
            transaction_id,
            attrs.get("transaction_time"),
        )

        cards = []
        related_transactions = []

        if network_raw:
            for block in network_raw:

                if "cards" in block:
                    cards.extend(block["cards"])

                if "related_tx" in block:
                    related_transactions.extend(
                        block["related_tx"]
                    )

        # Remove seed transaction if returned
        related_transactions = [
            tx
            for tx in related_transactions
            if tx.get("v_id") != transaction_id
        ]

        related_count = len(related_transactions)

        # -----------------------------------------
        # 3. NETWORK RISK SIGNAL
        # -----------------------------------------

        if related_count >= 20:
            score += 15
            signals.append(
                f"Large shared-card network: "
                f"{related_count} related transactions"
            )

        elif related_count >= 5:
            score += 10
            signals.append(
                f"Shared-card network: "
                f"{related_count} related transactions"
            )

        elif related_count > 0:
            score += 5
            signals.append(
                f"Shared-card network: "
                f"{related_count} related transactions"
            )

        # -----------------------------------------
        # 4. RISK LEVEL
        # -----------------------------------------

        score = min(score, 100)

        if score >= 60:
            risk_level = "HIGH"
        elif score >= 30:
            risk_level = "MEDIUM"
        elif score > 0:
            risk_level = "LOW"
        else:
            risk_level = "NO_SIGNAL"

        # -----------------------------------------
        # 5. RELATED TRANSACTION SUMMARY
        # -----------------------------------------

        related_summary = []

        for tx in related_transactions:

            tx_attrs = tx.get("attributes", {})

            related_summary.append({
                "transaction_id": tx.get("v_id"),
                "amount": tx_attrs.get("amount"),
                "transaction_time": tx_attrs.get(
                    "transaction_time"
                ),
                "merchant_pagerank": tx_attrs.get(
                    "mer_pagerank"
                ),
            })

        # -----------------------------------------
        # 6. FINAL RESPONSE
        # -----------------------------------------

        return {
            "transaction_id": attrs.get(
                "id",
                transaction_id
            ),

            "found": True,

            "risk_assessment": {
                "risk_score": score,
                "risk_level": risk_level
            },

            "transaction": {
                "amount": amount,
                "transaction_time": attrs.get(
                    "transaction_time"
                )
            },

            "fraud_signals": signals,

            "graph_features": {
                "indegree": attrs.get("indegree"),
                "outdegree": attrs.get("outdegree"),
                "shortest_path_length": attrs.get(
                    "shortest_path_length"
                ),
                "merchant_pagerank": attrs.get(
                    "mer_pagerank"
                ),
                "community_pagerank": attrs.get(
                    "cd_pagerank"
                )
            },

            "network_evidence": {
                "linked_cards": [
                    {
                        "card_id": card.get("v_id"),
                        "occupation": card.get(
                            "attributes", {}
                        ).get("occupation"),
                        "pagerank": card.get(
                            "attributes", {}
                        ).get("pagerank")
                    }
                    for card in cards
                ],

                "related_transaction_count":
                    related_count,

                # Keep the response manageable.
                "related_transactions":
                    related_summary[:20]
            }
        }

    # -----------------------------------------
    # 7. DEMO-FRIENDLY INVESTIGATION SUMMARY
    # -----------------------------------------

    def format_investigation_summary(self, result: dict) -> str:
        """Return a concise, demo-friendly investigation summary."""

        if not result.get("found"):
            return (
                "=== FRAUD INVESTIGATION ===\n"
                "Transaction not found\n"
                f"Transaction ID: {result.get('transaction_id')}"
            )

        risk = result["risk_assessment"]
        transaction = result["transaction"]
        network = result["network_evidence"]
        signals = result.get("fraud_signals", [])

        lines = [
            "=== FRAUD INVESTIGATION SUMMARY ===",
            f"Transaction ID  : {result['transaction_id']}",
            f"Amount          : {transaction['amount']}",
            f"Transaction Time: {transaction['transaction_time']}",
            "",
            f"Risk Score      : {risk['risk_score']}/100",
            f"Risk Level      : {risk['risk_level']}",
            "",
            "Fraud Signals:"
        ]

        if signals:
            for signal in signals:
                lines.append(f"  - {signal}")
        else:
            lines.append(
                "  - No significant fraud signals detected"
            )

        lines.extend([
            "",
            "Graph Evidence:",
            f"  - Linked cards: {len(network['linked_cards'])}",
            (
                "  - Historical related transactions: "
                f"{network['related_transaction_count']}"
            ),
        ])

        for card in network["linked_cards"]:
            lines.append(
                f"  - Card {card['card_id']} "
                f"(occupation: {card.get('occupation', 'Unknown')}, "
                f"pagerank: {card.get('pagerank', 0)})"
            )

        lines.append(
            "===================================="
        )

        return "\n".join(lines)


if __name__ == "__main__":

    analyzer = FraudAnalyzer()

    result = analyzer.analyze("832318")

    print("\n=== RAW FRAUD INVESTIGATION ===")
    print(result)

    print("\n")
    print(analyzer.format_investigation_summary(result))