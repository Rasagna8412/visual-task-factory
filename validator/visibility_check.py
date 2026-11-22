"""Visibility check & clipping audit module for Visual Task Factory (Milestone 2).

Audits ground_truth.json to confirm zero viewport clipping and reject any
partially occluded target whose Shapely visible area ratio is below 0.10
or above 0.90 (unless explicitly marked unanswerable).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union


class VisibilityAuditor:
    """Audits bounding boxes and Shapely visibility ratios against Milestone 2 standards."""

    def __init__(self, canvas_width: int = 1024, canvas_height: int = 1024) -> None:
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

    def audit_dict(self, gt_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        violations: List[str] = []
        nodes = gt_data.get("nodes", [])
        meta = gt_data.get("metadata", {})
        is_scene_unanswerable = meta.get("mode") == "unanswerable"

        stats = {
            "total_nodes": len(nodes),
            "unoccluded_count": 0,
            "partially_occluded_count": 0,
            "completely_occluded_count": 0,
            "unanswerable_targets": 0,
            "min_visible_ratio": 1.0,
            "max_visible_ratio": 0.0,
        }

        for node in nodes:
            nid = node.get("id", "unknown")
            bbox = node.get("bbox", [])
            area = float(node.get("area", 1.0))
            visible_area = float(node.get("visible_area", 0.0))
            is_partially = node.get("is_partially_occluded", False)
            is_completely = node.get("is_completely_occluded", False)
            is_unans = node.get("is_unanswerable_target", False)
            is_occ = node.get("is_occluded", False)

            # 1. Viewport clipping check
            if len(bbox) != 4:
                violations.append(f"Node {nid} has invalid bbox: {bbox}")
            else:
                x1, y1, x2, y2 = bbox
                if x1 < 0.0 or y1 < 0.0 or x2 > self.canvas_width or y2 > self.canvas_height:
                    violations.append(
                        f"Viewport clipping violation for node {nid}: bbox=[{x1}, {y1}, {x2}, {y2}] "
                        f"exceeds canvas bounds [0, 0, {self.canvas_width}, {self.canvas_height}]"
                    )

            # 2. Visibility ratio calculation
            vis_ratio = visible_area / area if area > 0 else 0.0
            if not is_unans:
                stats["min_visible_ratio"] = min(stats["min_visible_ratio"], vis_ratio)
                stats["max_visible_ratio"] = max(stats["max_visible_ratio"], vis_ratio)

            if is_unans:
                stats["unanswerable_targets"] += 1
                if vis_ratio > 0.001:
                    violations.append(
                        f"Abstention target {nid} is not 100% occluded: visible_ratio={vis_ratio:.4f}"
                    )
            elif is_partially:
                stats["partially_occluded_count"] += 1
                # Must be strictly between 0.10 and 0.90 visible
                if vis_ratio < 0.10 or vis_ratio > 0.90:
                    violations.append(
                        f"Node {nid} marked partially occluded but visible ratio {vis_ratio:.4f} "
                        f"is outside strict bounds [0.10, 0.90]"
                    )
            elif is_completely:
                stats["completely_occluded_count"] += 1
                if not is_scene_unanswerable and vis_ratio < 0.10:
                    violations.append(
                        f"Node {nid} is completely occluded (visible ratio {vis_ratio:.4f} < 0.10) "
                        f"in standard non-abstention scene"
                    )
            elif not is_occ:
                stats["unoccluded_count"] += 1
                if vis_ratio < 0.95:
                    violations.append(
                        f"Node {nid} marked unoccluded but visible ratio {vis_ratio:.4f} < 0.95"
                    )

        passed = len(violations) == 0
        return passed, violations, stats

    def audit_file(self, file_path: Union[str, Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
        p = Path(file_path)
        if not p.exists():
            return False, [f"File does not exist: {p}"], {}
        with open(p, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
        return self.audit_dict(gt_data)


def audit_ground_truth(
    source: Union[str, Path, Dict[str, Any]],
    canvas_width: int = 1024,
    canvas_height: int = 1024,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Convenience helper to audit ground truth dictionary or file."""
    auditor = VisibilityAuditor(canvas_width=canvas_width, canvas_height=canvas_height)
    if isinstance(source, dict):
        return auditor.audit_dict(source)
    else:
        return auditor.audit_file(source)


def main():
    parser = argparse.ArgumentParser(description="Audit ground_truth.json for clipping and occlusion bounds")
    parser.add_argument("path", type=str, help="Path to ground_truth.json or directory containing them")
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_dir():
        files = list(target.rglob("ground_truth.json"))
        if not files:
            print(f"No ground_truth.json files found in {target}")
            sys.exit(0)
    else:
        files = [target]

    all_passed = True
    auditor = VisibilityAuditor()
    print(f"\n[VisibilityAuditor] Auditing {len(files)} ground_truth file(s)...")

    for f in files:
        passed, violations, stats = auditor.audit_file(f)
        rel = f.name if len(files) == 1 else f.parent.name + "/" + f.name
        if passed:
            print(
                f"  PASS: {rel} (nodes: {stats['total_nodes']}, part_occ: {stats['partially_occluded_count']}, "
                f"unans: {stats['unanswerable_targets']})"
            )
        else:
            all_passed = False
            print(f"  REJECT: {rel}")
            for v in violations:
                print(f"    - {v}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
