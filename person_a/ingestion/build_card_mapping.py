from pathlib import Path
import pandas as pd


DATA_DIR = Path("data/raw")

CASES_FILE = DATA_DIR / "closed_cases_history.csv"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"


def main():

    cases = pd.read_csv(CASES_FILE)

    # Keep only historical cases that actually have transaction IDs.
    cases = cases.dropna(subset=["txn_ids", "card_id", "customer_id"])

    rows = []

    for _, case in cases.iterrows():

        txn_ids = str(case["txn_ids"]).split("|")

        for txn_id in txn_ids:
            try:
                txn_id = int(float(txn_id))
            except ValueError:
                continue

            rows.append(
                {
                    "case_id": case["case_id"],
                    "customer_id": case["customer_id"],
                    "card_id": case["card_id"],
                    "TransactionID": txn_id,
                }
            )

    mapping = pd.DataFrame(rows)

    transaction_ids = set(mapping["TransactionID"])

    print(f"Historical transaction IDs: {len(transaction_ids)}")

    matched = []

    for chunk in pd.read_csv(
        TRANSACTIONS_FILE,
        chunksize=50_000,
        low_memory=False,
    ):
        result = chunk[
            chunk["TransactionID"].isin(transaction_ids)
        ]

        if not result.empty:
            matched.append(result)

    transactions = pd.concat(
        matched,
        ignore_index=True
    )

    merged = mapping.merge(
        transactions[
            [
                "TransactionID",
                "customer_id",
                "card1",
                "card2",
                "card3",
                "card4",
                "card5",
                "card6",
            ]
        ],
        on=["TransactionID", "customer_id"],
        how="left",
    )

    print()
    print("=" * 100)
    print("CARD MAPPING")
    print("=" * 100)

    print(
        merged[
            [
                "case_id",
                "customer_id",
                "card_id",
                "TransactionID",
                "card1",
                "card2",
                "card3",
                "card4",
                "card5",
                "card6",
            ]
        ].head(100).to_string(index=False)
    )

    print()
    print("=" * 100)
    print("CARD ID -> CARD1 VALUES")
    print("=" * 100)

    summary = (
        merged
        .groupby(["customer_id", "card_id"])["card1"]
        .nunique()
        .reset_index(name="unique_card1_values")
    )

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()