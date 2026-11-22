"""Report generator module for Visual Task Factory (Milestone 3).

Generates 3 high-resolution (300 DPI) publication-grade diagnostic charts:
  1. accuracy_by_difficulty.png
  2. consistency_and_mcq_gap.png
  3. occlusion_dropoff.png
Exports benchmark_summary.json and report.md summary tables.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib
matplotlib.use("Agg")  # Headless rendering
import matplotlib.pyplot as plt
import numpy as np

# Professional technical palette
MODEL_COLORS = {
    "mock-frontier-strong": "#2563eb",  # Royal Blue
    "mock-frontier-mid": "#d97706",     # Amber / Orange
    "gpt-4o": "#10b981",                # Emerald
    "claude-3-5-sonnet": "#8b5cf6",     # Purple
    "gemini-1.5-pro": "#06b6d4",        # Cyan
}
FALLBACK_COLORS = ["#2563eb", "#d97706", "#10b981", "#8b5cf6", "#ec4899", "#6366f1"]


class ReportGenerator:
    """Generates diagnostic charts, JSON metrics, and markdown reports from benchmark results."""

    def __init__(self, output_dir: Union[str, Path] = "output/benchmark") -> None:
        self.output_dir = Path(output_dir)
        self.charts_dir = self.output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)

    def _get_color(self, model_name: str, idx: int) -> str:
        return MODEL_COLORS.get(model_name, FALLBACK_COLORS[idx % len(FALLBACK_COLORS)])

    def plot_accuracy_by_difficulty(self, metrics: Dict[str, Any]) -> Path:
        """Chart 1: Grouped bar chart comparing models across easy, medium, and hard difficulty."""
        fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=300)
        difficulties = ["easy", "medium", "hard"]
        display_diffs = ["Easy (12 nodes)", "Medium (28 nodes)", "Hard (52 nodes)"]

        models = list(metrics.keys())
        n_models = len(models)
        width = 0.8 / max(n_models, 1)
        x = np.arange(len(difficulties))

        for i, m in enumerate(models):
            diff_data = metrics[m].get("accuracy_by_difficulty", {})
            values = [diff_data.get(d, 0.0) for d in difficulties]
            offset = (i - (n_models - 1) / 2.0) * width
            bars = ax.bar(x + offset, values, width, label=m, color=self._get_color(m, i), alpha=0.9, edgecolor="#1e293b", linewidth=0.8)

            for bar in bars:
                h = bar.get_height()
                ax.annotate(f"{h:.1f}%", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 4), textcoords="offset points", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

        ax.set_title("VLM Accuracy Across Spatial Difficulty Tiers", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Open-Ended Accuracy (%)", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(display_diffs, fontsize=10, fontweight="bold")
        ax.set_ylim(0, 115)
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.legend(frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=9.5)
        plt.tight_layout()

        out_path = self.charts_dir / "accuracy_by_difficulty.png"
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        return out_path

    def plot_consistency_and_mcq_gap(self, metrics: Dict[str, Any]) -> Path:
        """Chart 2: Grouped bar chart showing Open-Ended vs MCQ vs Consistency vs Abstention."""
        fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
        dim_keys = ["open_ended_accuracy", "mcq_accuracy", "pairwise_consistency", "abstention_accuracy"]
        dim_labels = ["Open-Ended Acc", "MCQ Acc", "Pairwise Consistency", "Abstention Acc"]

        models = list(metrics.keys())
        n_models = len(models)
        width = 0.8 / max(n_models, 1)
        x = np.arange(len(dim_labels))

        for i, m in enumerate(models):
            m_data = metrics[m]
            values = [m_data.get(k, 0.0) for k in dim_keys]
            offset = (i - (n_models - 1) / 2.0) * width
            bars = ax.bar(x + offset, values, width, label=m, color=self._get_color(m, i), alpha=0.9, edgecolor="#1e293b", linewidth=0.8)

            for bar in bars:
                h = bar.get_height()
                ax.annotate(f"{h:.1f}%", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 4), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_title("Evaluation Primitives: MCQ Shortcut Gap & Counterfactual Consistency", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Score (%)", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(dim_labels, fontsize=10, fontweight="bold")
        ax.set_ylim(0, 115)
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.legend(frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=9.5)
        plt.tight_layout()

        out_path = self.charts_dir / "consistency_and_mcq_gap.png"
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        return out_path

    def plot_occlusion_dropoff(self, metrics: Dict[str, Any]) -> Path:
        """Chart 3: Accuracy drop-off curve plotted against exact Shapely occlusion percentage."""
        fig, ax = plt.subplots(figsize=(8.8, 5.2), dpi=300)
        bucket_keys = ["0-25%", "25-50%", "50-75%", "75-100%"]

        models = list(metrics.keys())
        x = np.arange(len(bucket_keys))

        for i, m in enumerate(models):
            b_data = metrics[m].get("accuracy_by_occlusion_bucket", {})
            values = [b_data.get(b, 0.0) for b in bucket_keys]
            color = self._get_color(m, i)
            line = ax.plot(x, values, marker="o", linewidth=2.5, markersize=7, label=m, color=color)

            for xi, yi in zip(x, values):
                ax.annotate(f"{yi:.1f}%", xy=(xi, yi), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8.5, fontweight="bold", color=color)

        ax.set_title("Accuracy Drop-Off vs. Shapely Spatial Occlusion Ratio", fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Shapely Visual Occlusion Bucket", fontsize=11, fontweight="bold", labelpad=8)
        ax.set_ylabel("Open-Ended Accuracy (%)", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(bucket_keys, fontsize=10, fontweight="bold")
        ax.set_ylim(0, 115)
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=9.5)
        plt.tight_layout()

        out_path = self.charts_dir / "occlusion_dropoff.png"
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        return out_path

    def export_summary_json(self, metrics: Dict[str, Any]) -> Path:
        """Exports benchmark_summary.json with complete metadata."""
        out_file = self.output_dir / "benchmark_summary.json"
        summary = {
            "metadata": {
                "benchmark": "Visual Task Factory - 2D Spatial Occlusion & Counting",
                "generated_at": datetime.datetime.now().isoformat(),
                "total_models_evaluated": len(metrics),
            },
            "models": metrics,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        return out_file

    def export_markdown_report(self, metrics: Dict[str, Any]) -> Path:
        """Exports report.md summary table and diagnostic analysis."""
        out_file = self.output_dir / "report.md"

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# Visual Task Factory: Milestone 3 Benchmark Evaluation Report",
            f"*Generated on: {now_str}*",
            "",
            "## 1. Executive Summary & Model Leaderboard",
            "",
            "| Model | Open-Ended Acc | MCQ Acc | MCQ Shortcut Gap | Pairwise Consistency | Abstention Acc | Hallucination Rate |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for m, d in metrics.items():
            gap_sign = "+" if d["mcq_shortcut_gap"] >= 0 else ""
            lines.append(
                f"| **{m}** | {d['open_ended_accuracy']}% | {d['mcq_accuracy']}% | "
                f"{gap_sign}{d['mcq_shortcut_gap']}% | {d['pairwise_consistency']}% | "
                f"{d['abstention_accuracy']}% | {d['hallucination_rate']}% |"
            )

        lines.extend([
            "",
            "## 2. Accuracy by Difficulty Tier",
            "",
            "| Model | Easy Tier | Medium Tier | Hard Tier |",
            "| :--- | :---: | :---: | :---: |",
        ])

        for m, d in metrics.items():
            diff = d.get("accuracy_by_difficulty", {})
            lines.append(f"| **{m}** | {diff.get('easy', 0.0)}% | {diff.get('medium', 0.0)}% | {diff.get('hard', 0.0)}% |")

        lines.extend([
            "",
            "## 3. Shapely Occlusion Sensitivity Curve",
            "",
            "| Model | 0% - 25% Occlusion | 25% - 50% Occlusion | 50% - 75% Occlusion | 75% - 100% Occlusion |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ])

        for m, d in metrics.items():
            occ = d.get("accuracy_by_occlusion_bucket", {})
            lines.append(
                f"| **{m}** | {occ.get('0-25%', 0.0)}% | {occ.get('25-50%', 0.0)}% | "
                f"{occ.get('50-75%', 0.0)}% | {occ.get('75-100%', 0.0)}% |"
            )

        lines.extend([
            "",
            "## 4. Key Findings & Diagnostic Observations",
            "",
            "1. **MCQ Shortcut Gap:** Models exhibit higher accuracy on multiple-choice questions compared to open-ended generation, reflecting guessing and process-of-elimination heuristics.",
            "2. **Pairwise Consistency:** Evaluating counterfactual twins reveals that weaker models often solve one twin while failing its flipped twin, exposing brittle pattern matching rather than true spatial grounding.",
            "3. **Abstention Reliability:** On 100% occluded targets (`cannot_determine`), models with lower abstention accuracy hallucinate shape and color attributes instead of acknowledging lack of visual information.",
            "4. **Occlusion Degradation:** Dense technical overlaps produce steep degradation curves as multi-layer occlusions conceal shape boundaries.",
            "",
            "## 5. Diagnostic Charts",
            "",
            "- `charts/accuracy_by_difficulty.png`",
            "- `charts/consistency_and_mcq_gap.png`",
            "- `charts/occlusion_dropoff.png`",
        ])

        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return out_file

    def generate_all(self, metrics: Dict[str, Any]) -> Dict[str, Path]:
        """Generates all charts, summary JSON, and report.md."""
        c1 = self.plot_accuracy_by_difficulty(metrics)
        c2 = self.plot_consistency_and_mcq_gap(metrics)
        c3 = self.plot_occlusion_dropoff(metrics)
        json_path = self.export_summary_json(metrics)
        md_path = self.export_markdown_report(metrics)

        return {
            "chart_difficulty": c1,
            "chart_consistency": c2,
            "chart_occlusion": c3,
            "summary_json": json_path,
            "report_md": md_path,
        }


def generate_benchmark_reports(
    metrics: Dict[str, Any], output_dir: Union[str, Path] = "output/benchmark"
) -> Dict[str, Path]:
    """Helper function to generate all reports and charts."""
    gen = ReportGenerator(output_dir=output_dir)
    return gen.generate_all(metrics)


def main():
    parser = argparse.ArgumentParser(description="Generate diagnostic charts and reports from benchmark summary")
    parser.add_argument("--summary-json", type=str, default="output/benchmark/benchmark_summary.json", help="Path to summary JSON")
    parser.add_argument("--output-dir", type=str, default="output/benchmark", help="Output directory")
    args = parser.parse_args()

    sum_path = Path(args.summary_json)
    if not sum_path.exists():
        print(f"Summary JSON not found: {sum_path}")
        sys.exit(1)

    with open(sum_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metrics = data.get("models", data)
    gen = ReportGenerator(output_dir=args.output_dir)
    paths = gen.generate_all(metrics)
    print(f"\n[ReportGenerator] Reports generated successfully:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
