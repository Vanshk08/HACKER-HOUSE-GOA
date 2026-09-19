from pathlib import Path
import pandas as pd


DATA_DIR = Path("data/raw")

CASE_FILE = DATA_DIR / "case_pack.csv"
TRANSACTION_FILE = DATA_DIR / "transactions.csv"


def main():
    cases = pd.read_csv(CASE_FILE)

    customers = set(cases["customer_id"].dropna())

    print(f"Benchmark customers: {len(customers)}")

    matches = []

    for chunk in pd.read_csv(
        TRANSACTION_FILE,
        chunksize=50_000,
        low_memory=False,
    ):
        rows = chunk[chunk["customer_id"].isin(customers)]

        if not rows.empty:
            matches.append(rows)

    transactions = pd.concat(matches, ignore_index=True)

    print(f"Matched transactions: {len(transactions)}")

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

    print("\nTransactions for benchmark customers:\n")

    print(
        transactions[columns]
        .sort_values(["customer_id", "TransactionDT"])
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()