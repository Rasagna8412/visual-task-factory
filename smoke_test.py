"""Smoke test for Milestone 2 of Visual Task Factory.

Generates:
  - 3 Counterfactual Pairs (easy, medium, hard) where a single surgical edit flips the answer
  - 1 Abstention case (mode='unanswerable') where the target shape is 100% occluded

Renders all 7 PNGs in ONE headless Chromium instance and runs both validators:
  1. Visibility & Clipping Auditor (strict [0.10, 0.90] visible ratio)
  2. Text-only Shortcut Filter (Ollama dolphin3:8b with mock fallback, 3 trials)

Prints a clean PASS/REJECT summary table.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from generator.scene_builder import SceneBuilder
from renderer.capture import BatchRenderer
from validator.shortcut_filter import ShortcutFilter
from validator.visibility_check import VisibilityAuditor

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def run_smoke_test(
    output_base_dir: Path | str = "output/smoke_test",
    mock_ollama: bool = False,
) -> bool:
    output_dir = Path(output_base_dir).resolve()
    print(f"\n================================================================================")
    print(f"       VISUAL TASK FACTORY - MILESTONE 2 COMPREHENSIVE SMOKE TEST")
    print(f"================================================================================")
    print(f"Output Directory: {output_dir}")
    print(f"Generating 3 Counterfactual Pairs (6 twins) + 1 Abstention Case (7 total)...\n")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    builder = SceneBuilder(config_path="config/difficulty_matrix.json")
    samples: List[Dict[str, Any]] = []
    render_batch_items: List[Tuple[Path, Path]] = []

    t_gen_start = time.time()

    # 1. Generate 3 Counterfactual Pairs:
    # Pair 1: seed 101, easy
    # Pair 2: seed 102, medium
    # Pair 3: seed 103, hard
    cf_configs = [
        (1, 101, "easy"),
        (2, 102, "medium"),
        (3, 103, "hard"),
    ]

    for pair_idx, seed, difficulty in cf_configs:
        base_scene, cf_scene = builder.generate_counterfactual_pair(seed=seed, difficulty=difficulty)

        # Save base
        base_folder = output_dir / f"pair_{pair_idx}_seed{seed}_{difficulty}_base"
        b_html, b_gt = builder.save(base_scene, base_folder)
        b_png = base_folder / "scene.png"
        samples.append({
            "name": f"pair_{pair_idx}_base",
            "type": "cf_base",
            "seed": seed,
            "difficulty": difficulty,
            "folder": base_folder,
            "html_path": b_html,
            "gt_path": b_gt,
            "png_path": b_png,
            "scene_data": base_scene,
            "pair_idx": pair_idx,
        })
        render_batch_items.append((b_html, b_png))

        # Save counterfactual
        cf_folder = output_dir / f"pair_{pair_idx}_seed{seed}_{difficulty}_counterfactual"
        c_html, c_gt = builder.save(cf_scene, cf_folder)
        c_png = cf_folder / "scene.png"
        samples.append({
            "name": f"pair_{pair_idx}_cf",
            "type": "cf_counterfactual",
            "seed": seed,
            "difficulty": difficulty,
            "folder": cf_folder,
            "html_path": c_html,
            "gt_path": c_gt,
            "png_path": c_png,
            "scene_data": cf_scene,
            "pair_idx": pair_idx,
        })
        render_batch_items.append((c_html, c_png))

    # 2. Generate 1 Abstention Case:
    # Seed 104, medium, unanswerable mode
    unans_seed = 104
    unans_diff = "medium"
    unans_scene = builder.generate(seed=unans_seed, difficulty=unans_diff, mode="unanswerable")
    unans_folder = output_dir / f"sample_abstention_seed{unans_seed}_{unans_diff}"
    u_html, u_gt = builder.save(unans_scene, unans_folder)
    u_png = unans_folder / "scene.png"
    samples.append({
        "name": "abstention_case",
        "type": "abstention",
        "seed": unans_seed,
        "difficulty": unans_diff,
        "folder": unans_folder,
        "html_path": u_html,
        "gt_path": u_gt,
        "png_path": u_png,
        "scene_data": unans_scene,
        "pair_idx": None,
    })
    render_batch_items.append((u_html, u_png))

    t_gen_end = time.time()
    print(f"[Generator] Generated {len(samples)} scenes and ground truth JSONs in {t_gen_end - t_gen_start:.2f}s.")

    # Batch render ALL 7 PNGs reusing ONE headless Chromium instance
    print(f"\n[Renderer] Launching single headless Chromium instance for batch capture...")
    t_render_start = time.time()
    with BatchRenderer(viewport_width=1024, viewport_height=1024) as renderer:
        rendered_pngs = renderer.render_batch(render_batch_items, verbose=True)
    t_render_end = time.time()
    print(f"[Renderer] Batch render of {len(rendered_pngs)} PNGs completed in {t_render_end - t_render_start:.2f}s.\n")

    # Automated Validation Gate & Evaluation Primitives Audit
    print(f"================================================================================")
    print(f"       AUTOMATED VALIDATION GATE & EVALUATION CHECKS")
    print(f"================================================================================")

    vis_auditor = VisibilityAuditor()
    sc_filter = ShortcutFilter(mock_ollama=mock_ollama)

    all_passed = True
    summary_rows = []

    # Check pair answer flips
    pair_targets: Dict[int, Dict[str, str]] = {}

    for item in samples:
        name = item["name"]
        seed = item["seed"]
        diff = item["difficulty"]
        png_p = item["png_path"]
        gt_data = item["scene_data"]
        sample_errors: List[str] = []

        # 1. PNG Verification
        if not png_p.exists() or png_p.stat().st_size < 1024:
            sample_errors.append("Invalid or missing PNG file")
        else:
            with open(png_p, "rb") as f:
                if f.read(8) != PNG_HEADER:
                    sample_errors.append("Invalid PNG file header")

        # 2. Visibility Check
        vis_pass, vis_violations, vis_stats = vis_auditor.audit_dict(gt_data)
        if not vis_pass:
            sample_errors.extend(vis_violations)

        # 3. Text-only Shortcut Filter (3 trials per question)
        sc_pass, sc_violations, sc_details = sc_filter.evaluate_dict(gt_data, trials_per_question=3)
        if not sc_pass:
            sample_errors.extend(sc_violations)

        # 4. Dual-format Q&A Check
        qa_pairs = gt_data.get("qa_pairs", [])
        if len(qa_pairs) != 3:
            sample_errors.append(f"Expected 3 Q&A pairs, got {len(qa_pairs)}")
        for qa in qa_pairs:
            if "open_ended" not in qa or "mcq" not in qa:
                sample_errors.append(f"Q&A {qa.get('question_id')} missing dual format (open_ended / mcq)")
            else:
                mcq = qa["mcq"]
                if len(mcq.get("options", {})) != 4:
                    sample_errors.append(f"MCQ options count != 4 for {qa.get('question_id')}")
                if mcq.get("correct_option") not in ["A", "B", "C", "D"]:
                    sample_errors.append(f"Invalid MCQ correct_option for {qa.get('question_id')}")

        # 5. Abstention Evaluation Check
        if item["type"] == "abstention":
            target_node = next((n for n in gt_data["nodes"] if n.get("is_unanswerable_target")), None)
            if not target_node:
                sample_errors.append("Abstention case missing target node")
            elif target_node.get("visible_area", 1.0) != 0.0:
                sample_errors.append(f"Abstention target node visible area != 0.0 ({target_node.get('visible_area')})")

            q1_ans = qa_pairs[0]["open_ended"]["answer"]
            if q1_ans != "cannot_determine":
                sample_errors.append(f"Abstention answer expected 'cannot_determine', got '{q1_ans}'")

        # Track counterfactual target answers
        if item["type"] in ["cf_base", "cf_counterfactual"]:
            p_idx = item["pair_idx"]
            target_ans = qa_pairs[0]["open_ended"]["answer"]
            if p_idx not in pair_targets:
                pair_targets[p_idx] = {}
            pair_targets[p_idx][item["type"]] = target_ans

        status = "PASS" if not sample_errors else "REJECT"
        if sample_errors:
            all_passed = False

        summary_rows.append({
            "name": name,
            "seed": seed,
            "diff": diff,
            "nodes": len(gt_data["nodes"]),
            "vis_gate": "PASS" if vis_pass else "FAIL",
            "sc_filter": "PASS" if sc_pass else "FAIL",
            "png_kb": f"{png_p.stat().st_size / 1024:.1f}",
            "status": status,
            "errors": sample_errors,
        })

    # Verify counterfactual flips
    for p_idx, answers in pair_targets.items():
        base_ans = answers.get("cf_base")
        cf_ans = answers.get("cf_counterfactual")
        if base_ans is None or cf_ans is None:
            all_passed = False
            print(f"ERROR: Incomplete pair {p_idx}: {answers}")
        elif base_ans == cf_ans:
            all_passed = False
            print(f"ERROR: Counterfactual pair {p_idx} failed to flip answer! Both are '{base_ans}'")
        else:
            print(f"[Verification] Pair {p_idx} answer flipped successfully: Base='{base_ans}' -> Counterfactual='{cf_ans}'")

    print("\n" + "-" * 88)
    print(f"{'Task / Sample':<24} | {'Seed':<5} | {'Diff':<7} | {'Nodes':<5} | {'Visibility':<10} | {'Shortcut':<8} | {'PNG':<8} | {'Status'}")
    print("-" * 88)
    for r in summary_rows:
        print(
            f"{r['name']:<24} | {r['seed']:<5} | {r['diff']:<7} | {r['nodes']:<5} | "
            f"{r['vis_gate']:<10} | {r['sc_filter']:<8} | {r['png_kb'] + ' KB':<8} | {r['status']}"
        )
        if r["errors"]:
            for err in r["errors"]:
                print(f"    -> ERROR: {err}")
    print("=" * 88)

    if all_passed:
        print(f"\n[SUCCESS] Milestone 2 passed! All 7 samples verified with zero errors.")
        print(f"Generated samples and ground truths located at: {output_dir}\n")
        return True
    else:
        print(f"\n[FAILURE] One or more samples failed Milestone 2 validation checks.\n")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Milestone 2 Smoke Test")
    parser.add_argument("--mock-ollama", action="store_true", help="Force mock LLM shortcut filter")
    args = parser.parse_args()

    success = run_smoke_test(mock_ollama=args.mock_ollama)
    sys.exit(0 if success else 1)
