"""Smoke test for Milestone 3 of Visual Task Factory.

Runs the Milestone 2 dataset through:
  1. Multi-VLM Benchmark Evaluator (testing mock-frontier-strong and mock-frontier-mid)
  2. Scoring Engine (Open-Ended vs MCQ, Pairwise Consistency, Abstention, Difficulty/Occlusion)
  3. Diagnostic Report Generator (generating 3 publication-grade 300 DPI charts and report.md)

Verifies all output logs, JSON summaries, and PNG charts with zero errors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from benchmark.evaluator import run_benchmark
from benchmark.report_generator import generate_benchmark_reports
from smoke_test import run_smoke_test

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def run_benchmark_smoke_test(
    dataset_dir: Path | str = "output/smoke_test",
    output_dir: Path | str = "output/benchmark",
) -> bool:
    dataset_p = Path(dataset_dir)
    output_p = Path(output_dir)

    print(f"\n================================================================================")
    print(f"       VISUAL TASK FACTORY - MILESTONE 3 BENCHMARK SMOKE TEST")
    print(f"================================================================================")
    print(f"Dataset Directory: {dataset_p.resolve()}")
    print(f"Benchmark Output Directory: {output_p.resolve()}")

    # Ensure smoke-test dataset exists
    if not dataset_p.exists() or len(list(dataset_p.glob("*/ground_truth.json"))) < 7:
        print("\n[Setup] Dataset missing or incomplete. Generating Milestone 2 smoke-test dataset...")
        run_smoke_test(output_base_dir=dataset_p, mock_ollama=True)

    task_count = len(list(dataset_p.glob("*/ground_truth.json")))
    print(f"\n[Evaluator] Discovered {task_count} validated benchmark tasks in dataset.")

    models_to_evaluate = ["mock-frontier-strong", "mock-frontier-mid"]
    print(f"[Evaluator] Evaluating models: {models_to_evaluate} across Open-Ended and MCQ modes...")

    t0 = time.time()
    raw_results, summary_metrics = run_benchmark(
        dataset_dir=dataset_p,
        output_dir=output_p,
        models=models_to_evaluate,
    )
    t_eval = time.time() - t0
    print(f"[Evaluator] Completed {len(raw_results)} queries across {len(models_to_evaluate)} models in {t_eval:.2f}s.")

    # Generate diagnostic charts and markdown reports
    print(f"\n[ReportGenerator] Rendering 3 high-resolution diagnostic charts (300 DPI)...")
    t0_rep = time.time()
    generated_files = generate_benchmark_reports(summary_metrics, output_dir=output_p)
    t_rep = time.time() - t0_rep
    print(f"[ReportGenerator] Diagnostic charts & report.md exported in {t_rep:.2f}s.")

    # Rigorous Verification Gate
    print(f"\n================================================================================")
    print(f"       BENCHMARK INTEGRITY & ARTIFACT VERIFICATION")
    print(f"================================================================================")

    verification_errors = []

    # 1. Verify raw_results.json
    raw_file = output_p / "raw_results.json"
    if not raw_file.exists() or raw_file.stat().st_size < 100:
        verification_errors.append(f"raw_results.json missing or empty: {raw_file}")
    else:
        with open(raw_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        if len(raw_data) != len(raw_results):
            verification_errors.append(f"raw_results count mismatch: {len(raw_data)} vs {len(raw_results)}")

    # 2. Verify benchmark_summary.json
    sum_file = output_p / "benchmark_summary.json"
    if not sum_file.exists() or sum_file.stat().st_size < 100:
        verification_errors.append(f"benchmark_summary.json missing or empty: {sum_file}")
    else:
        with open(sum_file, "r", encoding="utf-8") as f:
            sum_data = json.load(f)
        for m in models_to_evaluate:
            if m not in sum_data.get("models", {}):
                verification_errors.append(f"Model {m} missing from benchmark_summary.json")

    # 3. Verify report.md
    report_file = output_p / "report.md"
    if not report_file.exists() or report_file.stat().st_size < 200:
        verification_errors.append(f"report.md missing or empty: {report_file}")

    # 4. Verify all 3 PNG charts
    expected_charts = [
        "accuracy_by_difficulty.png",
        "consistency_and_mcq_gap.png",
        "occlusion_dropoff.png",
    ]
    charts_dir = output_p / "charts"
    for chart_name in expected_charts:
        chart_p = charts_dir / chart_name
        if not chart_p.exists():
            verification_errors.append(f"Chart missing: {chart_name}")
            continue
        chart_size = chart_p.stat().st_size
        if chart_size < 10000:
            verification_errors.append(f"Chart {chart_name} file size too small ({chart_size} bytes)")
        with open(chart_p, "rb") as f:
            if f.read(8) != PNG_HEADER:
                verification_errors.append(f"Chart {chart_name} has invalid PNG header")

    # Print summary leaderboard table
    print(f"\n{'-'*92}")
    print(f"{'Model Profile':<22} | {'Open Acc':<8} | {'MCQ Acc':<8} | {'MCQ Gap':<8} | {'Consistency':<11} | {'Abstention':<10} | {'Status'}")
    print(f"{'-'*92}")

    for m in models_to_evaluate:
        d = summary_metrics[m]
        gap_str = f"+{d['mcq_shortcut_gap']:.1f}%" if d['mcq_shortcut_gap'] >= 0 else f"{d['mcq_shortcut_gap']:.1f}%"
        status_str = "PASS" if not verification_errors else "FAIL"
        print(
            f"{m:<22} | {d['open_ended_accuracy']:>6.1f}% | {d['mcq_accuracy']:>6.1f}% | "
            f"{gap_str:>8} | {d['pairwise_consistency']:>9.1f}% | {d['abstention_accuracy']:>9.1f}% | {status_str}"
        )

    print(f"{'='*92}")

    # Print difficulty breakdown
    print(f"\nAccuracy Breakdown by Difficulty Tier:")
    for m in models_to_evaluate:
        d = summary_metrics[m]["accuracy_by_difficulty"]
        print(f"  {m:<22} -> Easy: {d.get('easy', 0.0):>5.1f}% | Medium: {d.get('medium', 0.0):>5.1f}% | Hard: {d.get('hard', 0.0):>5.1f}%")

    print(f"\nAccuracy Breakdown by Shapely Spatial Occlusion Bucket:")
    for m in models_to_evaluate:
        b = summary_metrics[m]["accuracy_by_occlusion_bucket"]
        print(f"  {m:<22} -> 0-25%: {b.get('0-25%', 0.0):>5.1f}% | 25-50%: {b.get('25-50%', 0.0):>5.1f}% | 50-75%: {b.get('50-75%', 0.0):>5.1f}% | 75-100%: {b.get('75-100%', 0.0):>5.1f}%")

    print(f"\nGenerated Diagnostic Charts (300 DPI):")
    for chart_name in expected_charts:
        cp = charts_dir / chart_name
        print(f"  - {cp.name} ({cp.stat().st_size / 1024:.1f} KB)")

    if verification_errors:
        print(f"\n[FAILURE] Verification errors encountered:")
        for err in verification_errors:
            print(f"  -> ERROR: {err}")
        return False

    print(f"\n[SUCCESS] Milestone 3 benchmark smoke test passed with zero errors!")
    print(f"Full benchmark results and diagnostic report located at: {output_p}\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Milestone 3 Benchmark Smoke Test")
    parser.add_argument("--dataset-dir", type=str, default="output/smoke_test", help="Dataset directory")
    parser.add_argument("--output-dir", type=str, default="output/benchmark", help="Benchmark output directory")
    args = parser.parse_args()

    success = run_benchmark_smoke_test(dataset_dir=args.dataset_dir, output_dir=args.output_dir)
    sys.exit(0 if success else 1)
