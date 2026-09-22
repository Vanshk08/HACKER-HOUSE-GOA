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
        attrs = transaction.get("attributes", {})
        customer_id = attrs.get("customer_id")
        card_id = self.client.card_id_from_attributes(attrs)

        score = 0
        signals = []

        amount = attrs.get("TransactionAmt", attrs.get("amount", 0))

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
        # 2. HHGOA GRAPH EVIDENCE
        # -----------------------------------------

        customer_raw = self.client.get_customer_history(customer_id) if customer_id else []
        card_raw = self.client.get_card_history(card_id) if card_id else []
        network_raw = self.client.get_related_transactions(card_id) if card_id else []
        cards = []
        related_transactions = []

        for block in customer_raw:
            cards.extend(block.get("cards", []))
        for block in card_raw:
            cards.extend(block.get("card", []))
        for block in network_raw:
            related_transactions.extend(block.get("txns", []))

        # Remove seed transaction if returned
        related_transactions = [
            tx
            for tx in related_transactions
            if str(tx.get("v_id")) != str(transaction_id)
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
                "merchant_pagerank": None,
            })

        region_evidence = []
        region_id = self.client.region_id_from_attributes(attrs)
        if region_id:
            try:
                for block in self.client.get_region_neighbors(region_id):
                    region_evidence.extend(block.get("region", []))
            except Exception:
                region_evidence = []

        similar_cases = []
        if customer_id:
            try:
                for block in self.client.get_similar_closed_cases(customer_id, "out_of_region_use"):
                    similar_cases.extend(block.get("cases", []))
            except Exception:
                similar_cases = []

        # HHGOA has no identity row or email value for some transactions. Only
        # expose evidence returned by the graph; never infer missing identities.
        email_evidence = []
        for field in ("P_emaildomain", "R_emaildomain"):
            domain = str(attrs.get(field, "") or "").strip()
            if domain:
                try:
                    for block in self.client.get_email_domain_neighbors("domain:" + domain.lower()):
                        email_evidence.extend(block.get("email", []))
                except Exception:
                    continue

        # -----------------------------------------
        # 6. FINAL RESPONSE
        # -----------------------------------------

        return {
            "transaction_id": attrs.get(
                "TransactionID",
                transaction_id
            ),

            "found": True,

            "risk_assessment": {
                "risk_score": score,
                "risk_level": risk_level
            },

            "transaction": {
                "amount": amount,
                "transaction_time": attrs.get("ts"),
                "customer_id": customer_id,
                "card_id": card_id,
                "risk_score": attrs.get("risk_score"),
                "channel": attrs.get("channel"),
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
                        "card_id": card.get("v_id") or card.get("attributes", {}).get("card_id"),
                        "occupation": None,
                        "pagerank": None,
                    }
                    for card in cards
                ],

                "related_transaction_count":
                    related_count,

                # Keep the response manageable.
                "related_transactions":
                    related_summary[:20]
            },
            "customer_history": customer_raw,
            "card_history": card_raw,
            "region_evidence": region_evidence,
            "email_evidence": email_evidence,
            "similar_prior_cases": similar_cases,
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