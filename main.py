"""Visual Task Factory - Single-Command Production Pipeline Entry Point.

Usage:
  python main.py --pairs 12 --abstentions 6 --seed 42 --mock-ollama --mock-vlm

Pipeline Stages:
  1. Deterministic Scene Generation (Counterfactual Pairs + Abstention Tasks)
  2. Batch Rendering (Single Headless Playwright Chromium Browser Instance)
  3. Validation Gate Audit (Shapely Visibility Check + Ollama Shortcut Filter)
  4. Multi-VLM Benchmark Evaluation (Open-Ended & MCQ Modes)
  5. Diagnostic Analytics & Publication Charts (300 DPI)
  6. Judge-Ready Demo Day Dashboard (dashboard.html)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.dashboard_builder import build_dashboard
from benchmark.evaluator import BenchmarkEvaluator
from benchmark.report_generator import generate_benchmark_reports
from generator.scene_builder import SceneBuilder
from renderer.capture import BatchRenderer
from validator.shortcut_filter import ShortcutFilter
from validator.visibility_check import VisibilityAuditor


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visual Task Factory - End-to-End Production Benchmark Generator & Evaluator"
    )
    parser.add_argument(
        "--pairs",
        type=int,
        default=12,
        help="Number of counterfactual pairs (default 12, evenly split across easy/med/hard)",
    )
    parser.add_argument(
        "--abstentions",
        type=int,
        default=6,
        help="Number of unanswerable abstention tasks (default 6)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Root integer seed for deterministic reproduction (default 42)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory path (default output/run_<seed>)",
    )
    parser.add_argument(
        "--mock-ollama",
        action="store_true",
        help="Use clean mock fallback for text-only shortcut filter",
    )
    parser.add_argument(
        "--mock-vlm",
        action="store_true",
        help="Run evaluation with simulated mock frontier profiles",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="mock-frontier-strong,mock-frontier-mid",
        help="Comma-separated model names to evaluate from config/models.json",
    )
    return parser.parse_args()


def run_pipeline(
    pairs_count: int = 12,
    abstentions_count: int = 6,
    root_seed: int = 42,
    output_dir: Optional[Union[str, Path]] = None,
    mock_ollama: bool = False,
    mock_vlm: bool = False,
    model_names: Optional[List[str]] = None,
) -> Path:
    t_start = time.time()
    out_dir = Path(output_dir or f"output/run_{root_seed}").resolve()
    dataset_dir = out_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    if model_names is None:
        model_names = ["mock-frontier-strong", "mock-frontier-mid"]

    print("\n" + "=" * 88)
    print("      VISUAL TASK FACTORY: END-TO-END BENCHMARK PRODUCTION PIPELINE")
    print("=" * 88)
    print(f"  Root Seed:         {root_seed}")
    print(f"  Target Pairs:      {pairs_count} (=> {pairs_count * 2} twin scenes)")
    print(f"  Abstentions:       {abstentions_count}")
    print(f"  Total Tasks:       {pairs_count * 2 + abstentions_count}")
    print(f"  Target Models:     {model_names}")
    print(f"  Output Directory:  {out_dir}")
    print("=" * 88 + "\n")

    builder = SceneBuilder(config_path="config/difficulty_matrix.json")
    generated_tasks: List[Dict[str, Any]] = []
    render_items: List[Tuple[Path, Path]] = []

    # -------------------------------------------------------------------------
    # Stage 1: Deterministic Scene Generation
    # -------------------------------------------------------------------------
    print(">>> [Stage 1/6] Generating Deterministic Counterfactual Pairs & Abstention Tasks...")
    t_stage1 = time.time()

    diff_cycle = ["easy", "medium", "hard"]

    # 1. Counterfactual Pairs
    for i in range(pairs_count):
        pair_idx = i + 1
        diff = diff_cycle[i % len(diff_cycle)]
        pair_seed = root_seed + (i + 1) * 37

        base_scene, cf_scene = builder.generate_counterfactual_pair(seed=pair_seed, difficulty=diff)

        base_folder = dataset_dir / f"pair_{pair_idx}_{diff}_base"
        b_html, b_gt = builder.save(base_scene, base_folder)
        b_png = base_folder / "scene.png"
        generated_tasks.append({
            "task_id": base_folder.name,
            "folder": base_folder,
            "html_path": b_html,
            "gt_path": b_gt,
            "png_path": b_png,
            "scene_data": base_scene,
            "gt_data": base_scene,
            "type": "cf_base",
            "pair_idx": pair_idx,
            "seed": pair_seed,
            "difficulty": diff,
        })
        render_items.append((b_html, b_png))

        cf_folder = dataset_dir / f"pair_{pair_idx}_{diff}_counterfactual"
        c_html, c_gt = builder.save(cf_scene, cf_folder)
        c_png = cf_folder / "scene.png"
        generated_tasks.append({
            "task_id": cf_folder.name,
            "folder": cf_folder,
            "html_path": c_html,
            "gt_path": c_gt,
            "png_path": c_png,
            "scene_data": cf_scene,
            "gt_data": cf_scene,
            "type": "cf_counterfactual",
            "pair_idx": pair_idx,
            "seed": pair_seed,
            "difficulty": diff,
        })
        render_items.append((c_html, c_png))

    # 2. Abstention Tasks
    for j in range(abstentions_count):
        abs_idx = j + 1
        diff = diff_cycle[j % len(diff_cycle)]
        abs_seed = root_seed + 1000 + (j + 1) * 41

        unans_scene = builder.generate(seed=abs_seed, difficulty=diff, mode="unanswerable")
        abs_folder = dataset_dir / f"abstention_{abs_idx}_{diff}"
        u_html, u_gt = builder.save(unans_scene, abs_folder)
        u_png = abs_folder / "scene.png"
        generated_tasks.append({
            "task_id": abs_folder.name,
            "folder": abs_folder,
            "html_path": u_html,
            "gt_path": u_gt,
            "png_path": u_png,
            "scene_data": unans_scene,
            "gt_data": unans_scene,
            "type": "abstention",
            "pair_idx": None,
            "seed": abs_seed,
            "difficulty": diff,
        })
        render_items.append((u_html, u_png))

    dt_stage1 = time.time() - t_stage1
    print(f"    Generated {len(generated_tasks)} tasks in {dt_stage1:.2f}s ({dt_stage1/len(generated_tasks)*1000:.1f}ms/task).\n")

    # -------------------------------------------------------------------------
    # Stage 2: Batch Rendering via ONE Headless Playwright Chromium Browser
    # -------------------------------------------------------------------------
    print(f">>> [Stage 2/6] Batch Rendering {len(render_items)} 1024x1024 PNGs via Single Chromium Instance...")
    t_stage2 = time.time()
    with BatchRenderer(viewport_width=1024, viewport_height=1024) as renderer:
        renderer.render_batch(render_items, verbose=False)
    dt_stage2 = time.time() - t_stage2
    print(f"    Batch render complete: {len(render_items)} images in {dt_stage2:.2f}s ({dt_stage2/len(render_items):.2f}s/img).\n")

    # -------------------------------------------------------------------------
    # Stage 3: Automated Validation Gate Audit
    # -------------------------------------------------------------------------
    print(">>> [Stage 3/6] Auditing Tasks against Automated Validation Gate...")
    t_stage3 = time.time()
    vis_auditor = VisibilityAuditor()
    sc_filter = ShortcutFilter(mock_ollama=mock_ollama)

    validated_tasks: List[Dict[str, Any]] = []
    rejected_tasks: List[Dict[str, Any]] = []

    for task in generated_tasks:
        gt_data = task["scene_data"]

        # Gate 1: Visibility & Clipping Audit
        vis_pass, vis_viol, _ = vis_auditor.audit_dict(gt_data)

        # Gate 2: Shortcut Filter (3 trials)
        sc_pass, sc_viol, _ = sc_filter.evaluate_dict(gt_data, trials_per_question=3)

        if vis_pass and sc_pass:
            validated_tasks.append(task)
        else:
            task["rejection_reasons"] = vis_viol + sc_viol
            rejected_tasks.append(task)

    dt_stage3 = time.time() - t_stage3
    print(f"    Validation Gate Audit complete in {dt_stage3:.2f}s:")
    print(f"      • PASSED:   {len(validated_tasks)} / {len(generated_tasks)} tasks ({len(validated_tasks)/len(generated_tasks)*100:.1f}%)")
    print(f"      • REJECTED: {len(rejected_tasks)} / {len(generated_tasks)} tasks")
    if rejected_tasks:
        for rj in rejected_tasks:
            print(f"        -> Dropped {rj['task_id']}: {rj['rejection_reasons']}")
    print()

    # -------------------------------------------------------------------------
    # Stage 4: Multi-VLM Benchmark Evaluation
    # -------------------------------------------------------------------------
    print(f">>> [Stage 4/6] Running Multi-VLM Benchmark across {model_names}...")
    t_stage4 = time.time()
    evaluator = BenchmarkEvaluator(output_dir=out_dir)

    import asyncio
    from benchmark.vlm_client import get_vlm_client

    async def _evaluate_all() -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for model_name in model_names:
            client = get_vlm_client(model=model_name)
            for task in validated_tasks:
                task_res = await evaluator.evaluate_task(client, task)
                results.extend(task_res)
        return results

    all_raw_results = asyncio.run(_evaluate_all())

    # Save raw results
    raw_results_file = out_dir / "raw_results.json"
    with open(raw_results_file, "w", encoding="utf-8") as f:
        json.dump(all_raw_results, f, indent=2)

    summary_metrics = evaluator.compute_metrics(all_raw_results)
    dt_stage4 = time.time() - t_stage4
    print(f"    Evaluated {len(all_raw_results)} queries in {dt_stage4:.2f}s.\n")

    # -------------------------------------------------------------------------
    # Stage 5: Diagnostic Report & Charts Generation
    # -------------------------------------------------------------------------
    print(">>> [Stage 5/6] Generating 300 DPI Publication Charts & Markdown Report...")
    t_stage5 = time.time()
    report_paths = generate_benchmark_reports(summary_metrics, output_dir=out_dir)
    dt_stage5 = time.time() - t_stage5
    print(f"    Exported diagnostic charts & summary in {dt_stage5:.2f}s.\n")

    # -------------------------------------------------------------------------
    # Stage 6: Demo Day HTML Dashboard
    # -------------------------------------------------------------------------
    print(">>> [Stage 6/6] Building Self-Contained Demo Day Dashboard (dashboard.html)...")
    t_stage6 = time.time()
    dashboard_path = build_dashboard(
        run_dir=out_dir,
        summary_metrics=summary_metrics,
        raw_results=all_raw_results,
    )
    dt_stage6 = time.time() - t_stage6
    print(f"    Dashboard generated: {dashboard_path.name} ({dashboard_path.stat().st_size / 1024:.1f} KB) in {dt_stage6:.2f}s.\n")

    total_time = time.time() - t_start

    # -------------------------------------------------------------------------
    # Final Benchmark Executive Summary
    # -------------------------------------------------------------------------
    print("=" * 88)
    print("                    BENCHMARK EXECUTIVE LEADERBOARD")
    print("=" * 88)
    print(f"{'Model':<22} | {'Open Acc':<8} | {'MCQ Acc':<8} | {'MCQ Gap':<8} | {'Consistency':<11} | {'Abstention':<10}")
    print("-" * 88)
    for m in model_names:
        d = summary_metrics.get(m, {})
        gap_sign = "+" if d.get("mcq_shortcut_gap", 0) >= 0 else ""
        print(
            f"{m:<22} | {d.get('open_ended_accuracy', 0):>6.1f}% | {d.get('mcq_accuracy', 0):>6.1f}% | "
            f"{gap_sign}{d.get('mcq_shortcut_gap', 0):>6.1f}% | {d.get('pairwise_consistency', 0):>9.1f}% | "
            f"{d.get('abstention_accuracy', 0):>9.1f}%"
        )
    print("=" * 88)
    print(f"\nPipeline finished in {total_time:.2f}s.")
    print(f"Artifacts ready:")
    print(f"  • HTML Dashboard: {dashboard_path}")
    print(f"  • Markdown Report: {out_dir / 'report.md'}")
    print(f"  • Summary Metrics: {out_dir / 'benchmark_summary.json'}")
    print(f"  • Raw Results:     {raw_results_file}")
    print(f"  • Charts Folder:   {out_dir / 'charts'}\n")

    return out_dir


def main():
    args = parse_arguments()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.mock_vlm and not models:
        models = ["mock-frontier-strong", "mock-frontier-mid"]

    run_pipeline(
        pairs_count=args.pairs,
        abstentions_count=args.abstentions,
        root_seed=args.seed,
        output_dir=args.output,
        mock_ollama=args.mock_ollama,
        mock_vlm=args.mock_vlm,
        model_names=models,
    )


if __name__ == "__main__":
    main()
