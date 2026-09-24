"""
Convert existing results (results/HHG-001.json - HHG-020.json)
into submission cases/HHG-001.json - HHG-020.json strictly adhering to the README format.

DOES NOT call any LLMs.
DOES NOT modify results/ or re-run any investigations.
"""

import os
import sys
import json
import glob
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from schemas.output_adapter import adapt_existing_result_to_case_contract


def convert_all_results(
    results_dir: str = "results",
    output_dir: str = "cases",
) -> list[str]:
    """Reads all completed cases from results_dir and writes formatted cases to output_dir."""
    results_path = os.path.join(PROJECT_ROOT, results_dir)
    output_path = os.path.join(PROJECT_ROOT, output_dir)
    os.makedirs(output_path, exist_ok=True)

    file_pattern = os.path.join(results_path, "HHG-*.json")
    files = sorted(glob.glob(file_pattern))

    if not files:
        raise FileNotFoundError(f"No result files matching {file_pattern} found.")

    converted_files = []
    print("=" * 80)
    print(f"CONVERTING EXISTING RESULTS -> SUBMISSION CASES ({len(files)} cases)")
    print(f"Source: {results_path}")
    print(f"Target: {output_path}")
    print("=" * 80)

    for fpath in files:
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as fp:
            raw_result = json.load(fp)

        # Adapt existing result without calling LLM
        adapted = adapt_existing_result_to_case_contract(raw_result)

        out_file = os.path.join(output_path, fname)
        with open(out_file, "w", encoding="utf-8") as fp:
            json.dump(adapted, fp, indent=2)

        converted_files.append(out_file)
        c = adapted["case"]
        nba = adapted["next_best_actions"]
        sar = adapted["sar"]
        print(
            f"Converted {fname} -> {out_file} | "
            f"verdict={c['verdict']:<16} | "
            f"pattern={c['pattern']:<26} | "
            f"exp=${c['exposure_usd']:<8.2f} | "
            f"actions={len(nba['final'])} | "
            f"sar_file={sar['file']}"
        )

    print("=" * 80)
    print(f"Successfully converted {len(converted_files)} cases into {output_path}/")
    print("=" * 80)
    return converted_files


if __name__ == "__main__":
    convert_all_results()
