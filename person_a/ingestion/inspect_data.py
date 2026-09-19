from pathlib import Path
import pandas as pd


DATA_DIR = Path("data/raw")


def inspect_file(filename: str):
    path = DATA_DIR / filename

    print("\n" + "=" * 80)
    print(f"FILE: {filename}")
    print("=" * 80)

    if not path.exists():
        print(f"❌ File not found: {path}")
        return

    # Read only the header first.
    # This avoids loading the huge transactions.csv into memory.
    columns = pd.read_csv(path, nrows=0).columns

    print(f"Number of columns: {len(columns)}")

    print("\nColumns:")
    for i, column in enumerate(columns, start=1):
        print(f"{i:3}. {column}")

    print("\nFirst 5 rows:")
    sample = pd.read_csv(path, nrows=5)
    print(sample.to_string(index=False))


if __name__ == "__main__":

    files = [
        "transactions.csv",
        "identity.csv",
        "closed_cases_history.csv",
        "case_pack.csv",
    ]

    for filename in files:
        inspect_file(filename)