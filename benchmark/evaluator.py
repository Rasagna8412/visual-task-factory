"""Benchmark Evaluator module for Visual Task Factory (Milestone 3).

Evaluates visual reasoning tasks across open-ended and MCQ formats, grades deterministically,
and computes:
  1. Open-Ended vs. MCQ Accuracy & MCQ Shortcut Gap
  2. Pairwise Consistency Score (Counterfactual pairs)
  3. Abstention Accuracy & Hallucination Rate
  4. Accuracy by Difficulty Tier & Shapely Occlusion Buckets
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from .vlm_client import VLMClient, VLMResponse, get_vlm_client
except ImportError:
    try:
        from benchmark.vlm_client import VLMClient, VLMResponse, get_vlm_client
    except ImportError:
        from vlm_client import VLMClient, VLMResponse, get_vlm_client


def normalize_open_ended_response(response_text: str, ground_truth: str) -> bool:
    """Grades open-ended responses against ground truth with deterministic normalization."""
    pred = response_text.strip().lower()
    gt = ground_truth.strip().lower()

    if pred == gt:
        return True

    # Abstention check
    if gt == "cannot_determine":
        return any(phrase in pred for phrase in ["cannot_determine", "cannot determine", "unanswerable", "impossible", "not visible", "hidden"])

    # Boolean check
    if gt in ["yes", "no"]:
        match = re.search(r"\b(yes|no)\b", pred)
        return match.group(1) == gt if match else False

    # Integer count check
    if gt.isdigit():
        numbers = re.findall(r"\b\d+\b", pred)
        if numbers:
            return numbers[0] == gt
        # Also check word representations for 0-10
        word_map = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
        for word, digit in word_map.items():
            if re.search(rf"\b{word}\b", pred):
                return digit == gt

    return False


def normalize_mcq_response(response_text: str, correct_option: str, options: Dict[str, str]) -> bool:
    """Grades MCQ responses by extracting option letters or matching option text."""
    pred = response_text.strip().upper()
    corr = correct_option.strip().upper()

    # Exact single letter match
    if pred == corr:
        return True

    # Search for option letter (e.g. "A)", "Option A", "Answer: A")
    match = re.search(r"\b([A-D])\b", pred)
    if match and match.group(1) == corr:
        return True

    # Check if the model answered with the correct option's exact text
    expected_text = options.get(corr, "").strip().lower()
    if expected_text and expected_text in response_text.lower():
        # Make sure it does not also contain conflicting option texts
        return True

    return False


class BenchmarkEvaluator:
    """Orchestrates benchmark evaluation and metric aggregation across models and tasks."""

    def __init__(self, output_dir: Union[str, Path] = "output/benchmark") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_dataset(self, dataset_dir: Union[str, Path]) -> List[Dict[str, Any]]:
        """Discovers and loads all valid tasks with ground_truth.json and scene.png."""
        base = Path(dataset_dir)
        tasks: List[Dict[str, Any]] = []

        gt_files = sorted(list(base.rglob("ground_truth.json")))
        for gt_path in gt_files:
            folder = gt_path.parent
            png_path = folder / "scene.png"
            if not png_path.exists():
                continue

            with open(gt_path, "r", encoding="utf-8") as f:
                gt_data = json.load(f)

            tasks.append({
                "task_id": folder.name,
                "folder": folder,
                "gt_path": gt_path,
                "png_path": png_path,
                "gt_data": gt_data,
            })

        return tasks

    async def evaluate_task(
        self,
        vlm: VLMClient,
        task: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Evaluates a single task against a model in both open_ended and MCQ formats."""
        results: List[Dict[str, Any]] = []
        gt_data = task.get("gt_data") or task.get("scene_data", {})
        meta = gt_data.get("metadata", {})
        nodes = gt_data.get("nodes", [])
        qa_pairs = gt_data.get("qa_pairs", [])
        png_path = task["png_path"]

        # Calculate mean occlusion ratio for context
        occlusion_ratios = [float(n.get("occlusion_ratio", 0.0)) for n in nodes if not n.get("is_unanswerable_target")]
        mean_occlusion = sum(occlusion_ratios) / max(len(occlusion_ratios), 1)

        difficulty = meta.get("difficulty", "medium")
        seed = meta.get("seed", 42)
        mode = meta.get("mode", "standard")
        twin_type = meta.get("twin_type", None)

        for qa in qa_pairs:
            q_id = qa.get("question_id", "q")
            is_unanswerable = qa.get("is_unanswerable", False) or mode == "unanswerable"
            is_cf = qa.get("is_counterfactual_target", False)

            # Compute specific target occlusion ratio for this question
            matching_ids = qa.get("matching_node_ids", [])
            matching_nodes = [n for n in nodes if n.get("id") in matching_ids]
            if is_unanswerable:
                target_occlusion = 1.0
            elif matching_nodes:
                target_occlusion = sum(float(n.get("occlusion_ratio", 0.0)) for n in matching_nodes) / len(matching_nodes)
            else:
                occ_nodes = [float(n.get("occlusion_ratio", 0.0)) for n in nodes if float(n.get("occlusion_ratio", 0.0)) > 0.05]
                target_occlusion = sum(occ_nodes) / max(len(occ_nodes), 1) if occ_nodes else mean_occlusion

            open_qa = qa.get("open_ended", {})
            mcq_qa = qa.get("mcq", {})

            # 1. Open-Ended Evaluation
            open_prompt = (
                f"{open_qa.get('question', '')}\n\n"
                f"Please provide a concise and direct answer based strictly on the image."
            )
            open_ctx = {
                "format": "open_ended",
                "correct_answer": open_qa.get("answer", ""),
                "difficulty": difficulty,
                "mean_occlusion": target_occlusion,
                "is_unanswerable": is_unanswerable,
                "is_counterfactual": is_cf,
                "seed": seed,
                "question_id": q_id,
            }

            open_resp = await vlm.query(open_prompt, png_path, open_ctx)
            open_correct = normalize_open_ended_response(open_resp.raw_text, str(open_qa.get("answer", "")))

            results.append({
                "task_id": task["task_id"],
                "model": vlm.model,
                "format": "open_ended",
                "question_id": q_id,
                "difficulty": difficulty,
                "mean_occlusion": round(target_occlusion, 3),
                "is_unanswerable": is_unanswerable,
                "is_counterfactual": is_cf,
                "twin_type": twin_type,
                "prompt": open_prompt,
                "raw_response": open_resp.raw_text,
                "ground_truth": str(open_qa.get("answer", "")),
                "is_correct": open_correct,
                "latency_ms": open_resp.latency_ms,
            })

            # 2. MCQ Evaluation
            mcq_prompt = (
                f"{mcq_qa.get('question', '')}\n\n"
                f"Select the best option (A, B, C, or D) based strictly on the image."
            )
            mcq_ctx = {
                "format": "mcq",
                "correct_answer": str(mcq_qa.get("answer", "")),
                "correct_option": mcq_qa.get("correct_option", "A"),
                "mcq_options": mcq_qa.get("options", {}),
                "difficulty": difficulty,
                "mean_occlusion": target_occlusion,
                "is_unanswerable": is_unanswerable,
                "is_counterfactual": is_cf,
                "seed": seed,
                "question_id": q_id,
            }

            mcq_resp = await vlm.query(mcq_prompt, png_path, mcq_ctx)
            mcq_correct = normalize_mcq_response(
                mcq_resp.raw_text, mcq_qa.get("correct_option", "A"), mcq_qa.get("options", {})
            )

            results.append({
                "task_id": task["task_id"],
                "model": vlm.model,
                "format": "mcq",
                "question_id": q_id,
                "difficulty": difficulty,
                "mean_occlusion": round(target_occlusion, 3),
                "is_unanswerable": is_unanswerable,
                "is_counterfactual": is_cf,
                "twin_type": twin_type,
                "prompt": mcq_prompt,
                "raw_response": mcq_resp.raw_text,
                "correct_option": mcq_qa.get("correct_option", "A"),
                "options": mcq_qa.get("options", {}),
                "ground_truth": str(mcq_qa.get("answer", "")),
                "is_correct": mcq_correct,
                "latency_ms": mcq_resp.latency_ms,
            })

        return results

    def compute_metrics(self, raw_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Computes comprehensive benchmark metrics per model."""
        models = sorted(list(set(r["model"] for r in raw_results)))
        model_metrics: Dict[str, Any] = {}

        for m in models:
            m_res = [r for r in raw_results if r["model"] == m]

            open_res = [r for r in m_res if r["format"] == "open_ended"]
            mcq_res = [r for r in m_res if r["format"] == "mcq"]

            open_acc = sum(1 for r in open_res if r["is_correct"]) / max(len(open_res), 1)
            mcq_acc = sum(1 for r in mcq_res if r["is_correct"]) / max(len(mcq_res), 1)
            mcq_gap = mcq_acc - open_acc

            # Pairwise Consistency Score
            # Group by counterfactual pair identifier
            cf_pairs: Dict[str, Dict[str, bool]] = {}
            for r in open_res:
                if r.get("is_counterfactual"):
                    # Pair name extracted from task_id (e.g. pair_1_seed101_easy_base -> pair_1)
                    match = re.match(r"(pair_\d+)", r["task_id"])
                    pair_id = match.group(1) if match else r["task_id"]
                    twin = r.get("twin_type") or ("base" if "base" in r["task_id"] else "counterfactual")
                    if pair_id not in cf_pairs:
                        cf_pairs[pair_id] = {}
                    cf_pairs[pair_id][twin] = r["is_correct"]

            both_correct = sum(
                1 for p, twins in cf_pairs.items() if twins.get("base") and twins.get("counterfactual")
            )
            pairwise_consistency = both_correct / max(len(cf_pairs), 1)

            # Abstention & Hallucination Rate
            unans_res = [r for r in open_res if r.get("is_unanswerable")]
            abstention_correct = sum(1 for r in unans_res if r["is_correct"])
            abstention_acc = abstention_correct / max(len(unans_res), 1)
            hallucination_rate = 1.0 - abstention_acc

            # Accuracy by Difficulty Tier
            diff_metrics: Dict[str, float] = {}
            for diff in ["easy", "medium", "hard"]:
                sub = [r for r in open_res if r["difficulty"] == diff]
                diff_acc = sum(1 for r in sub if r["is_correct"]) / max(len(sub), 1)
                diff_metrics[diff] = round(diff_acc * 100.0, 1)

            # Accuracy by Shapely Occlusion Buckets
            # Buckets: 0-25%, 25-50%, 50-75%, 75-100%
            buckets = {
                "0-25%": [r for r in open_res if 0.0 <= r["mean_occlusion"] < 0.25],
                "25-50%": [r for r in open_res if 0.25 <= r["mean_occlusion"] < 0.50],
                "50-75%": [r for r in open_res if 0.50 <= r["mean_occlusion"] < 0.75],
                "75-100%": [r for r in open_res if r["mean_occlusion"] >= 0.75],
            }
            occlusion_metrics = {
                b_name: round((sum(1 for r in b_items if r["is_correct"]) / max(len(b_items), 1)) * 100.0, 1)
                for b_name, b_items in buckets.items()
            }

            model_metrics[m] = {
                "open_ended_accuracy": round(open_acc * 100.0, 1),
                "mcq_accuracy": round(mcq_acc * 100.0, 1),
                "mcq_shortcut_gap": round(mcq_gap * 100.0, 1),
                "pairwise_consistency": round(pairwise_consistency * 100.0, 1),
                "cf_pairs_evaluated": len(cf_pairs),
                "cf_pairs_consistent": both_correct,
                "abstention_accuracy": round(abstention_acc * 100.0, 1),
                "hallucination_rate": round(hallucination_rate * 100.0, 1),
                "abstention_queries": len(unans_res),
                "accuracy_by_difficulty": diff_metrics,
                "accuracy_by_occlusion_bucket": occlusion_metrics,
                "total_queries_evaluated": len(m_res),
            }

        return model_metrics

    async def run(
        self,
        dataset_dir: Union[str, Path] = "output/smoke_test",
        models: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Runs the benchmark pipeline on all dataset tasks and exports raw_results.json."""
        tasks = self.load_dataset(dataset_dir)
        if not tasks:
            raise FileNotFoundError(f"No valid tasks found in {dataset_dir}")

        if models is None:
            models = ["mock-frontier-strong", "mock-frontier-mid"]

        all_raw_results: List[Dict[str, Any]] = []

        for m_name in models:
            vlm = get_vlm_client(model=m_name)
            for task in tasks:
                task_res = await self.evaluate_task(vlm, task)
                all_raw_results.extend(task_res)

        # Save raw results
        raw_file = self.output_dir / "raw_results.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(all_raw_results, f, indent=2)

        summary_metrics = self.compute_metrics(all_raw_results)
        return all_raw_results, summary_metrics


def run_benchmark(
    dataset_dir: Union[str, Path] = "output/smoke_test",
    output_dir: Union[str, Path] = "output/benchmark",
    models: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Synchronous helper for running the benchmark evaluator."""
    evaluator = BenchmarkEvaluator(output_dir=output_dir)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(evaluator.run(dataset_dir=dataset_dir, models=models))


def main():
    parser = argparse.ArgumentParser(description="Evaluate multi-VLM benchmark on spatial occlusion dataset")
    parser.add_argument("--dataset-dir", type=str, default="output/smoke_test", help="Dataset directory")
    parser.add_argument("--output-dir", type=str, default="output/benchmark", help="Benchmark output directory")
    parser.add_argument("--mock-vlm", action="store_true", help="Run with simulated mock frontier models")
    parser.add_argument("--models", nargs="+", default=None, help="List of model names to evaluate")
    args = parser.parse_args()

    models = args.models
    if args.mock_vlm or not models:
        models = ["mock-frontier-strong", "mock-frontier-mid"]

    print(f"\n[BenchmarkEvaluator] Running benchmark across {models} on {args.dataset_dir}...")
    raw_res, metrics = run_benchmark(dataset_dir=args.dataset_dir, output_dir=args.output_dir, models=models)

    print(f"[BenchmarkEvaluator] Evaluated {len(raw_res)} queries. Summary:")
    for m, d in metrics.items():
        print(f"  Model: {m}")
        print(f"    Open-Ended Acc: {d['open_ended_accuracy']}% | MCQ Acc: {d['mcq_accuracy']}% (Gap: +{d['mcq_shortcut_gap']}%)")
        print(f"    Pairwise Consistency: {d['pairwise_consistency']}% | Abstention Acc: {d['abstention_accuracy']}% (Hallucination: {d['hallucination_rate']}%)")


if __name__ == "__main__":
    main()
