"""
CLI Runner for Round 3 Improvement 2: Ground-Truth Citation-Support Evaluation Harness.
Executes the benchmark and writes the results to data/benchmarks/round3_evaluation_results.json.

Usage:
    python scripts/run_evaluation_harness.py
"""

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.modules.evaluation.harness import run_payflow_evaluation_harness  # noqa: E402


def main() -> None:
    report = run_payflow_evaluation_harness()
    out_path = ROOT_DIR / "data" / "benchmarks" / "round3_evaluation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(f"Benchmark completed and written to {out_path}")
    print(f"Baseline Precision: {report.baselineMetrics.extractionPrecision} | Post-Improvement Precision: {report.postImprovementMetrics.extractionPrecision}")
    print(f"Baseline Mismatch Detection: {report.baselineMetrics.citationMismatchDetectionRate} | Post-Improvement Mismatch Detection: {report.postImprovementMetrics.citationMismatchDetectionRate}")


if __name__ == "__main__":
    main()
