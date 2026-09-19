from pathlib import Path
import pandas as pd


DATA_DIR = Path("data/raw")

CASE_FILE = DATA_DIR / "case_pack.csv"
TRANSACTION_FILE = DATA_DIR / "transactions.csv"


def main():
    print("Loading case pack...")

    cases = pd.read_csv(CASE_FILE)

    print(f"Number of benchmark cases: {len(cases)}")
    print()

    print("Case pack:")
    print(
        cases[
            [
                "case_id",
                "flagged_txn_id",
                "card_id",
                "customer_id",
                "risk_score",
            ]
        ].to_string(index=False)
    )

    transaction_ids = cases["flagged_txn_id"].dropna().tolist()

    print()
    print("Searching transactions...")

    matched = []

    # Read the large transaction file in chunks.
    for chunk in pd.read_csv(
        TRANSACTION_FILE,
        chunksize=50_000,
        low_memory=False,
    ):
        rows = chunk[chunk["TransactionID"].isin(transaction_ids)]

        if not rows.empty:
            matched.append(rows)

    if not matched:
        print("No transactions found.")
        return

    transactions = pd.concat(matched, ignore_index=True)

    print()
    print("=" * 80)
    print("FLAGGED TRANSACTIONS")
    print("=" * 80)

    columns = [
        "TransactionID",
        "TransactionDT",
        "TransactionAmt",
        "ProductCD",
        "card1",
        "card2",
        "card3",
        "card4",
        "card5",
        "card6",
        "addr1",
        "addr2",
        "P_emaildomain",
        "R_emaildomain",
        "customer_id",
        "ts",
        "channel",
        "risk_score",
    ]

    print(transactions[columns].to_string(index=False))


if __name__ == "__main__":
    main()