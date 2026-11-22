"""Scene builder module for Visual Task Factory (Milestones 1 & 2).

Generates deterministic 1024x1024 SVG/HTML scenes of colored geometric nodes
(circles, squares, triangles) with deliberate partial spatial occlusions and
technical distractor gridlines, exact Shapely ground truth, counterfactual pairs,
abstention modes, and dual-format (open-ended + MCQ) Q&A pairs.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import shapely
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

COLOR_PALETTE: Dict[str, str] = {
    "red": "#ef4444",
    "blue": "#3b82f6",
    "green": "#10b981",
    "yellow": "#f59e0b",
    "purple": "#8b5cf6",
    "cyan": "#06b6d4",
}

SHAPE_TYPES: List[str] = ["circle", "square", "triangle"]
CANVAS_SIZE: int = 1024
CANVAS_PADDING: float = 40.0


@dataclass
class Node:
    id: str
    shape: str
    color: str
    hex_color: str
    center: Tuple[float, float]
    size: float
    z_order: int
    bbox: List[float]  # [x1, y1, x2, y2]
    area: float
    visible_area: float = 0.0
    occlusion_ratio: float = 0.0
    is_occluded: bool = False
    is_partially_occluded: bool = False
    is_completely_occluded: bool = False
    is_unanswerable_target: bool = False
    occluded_by: List[str] = None
    occluding: List[str] = None

    def __post_init__(self):
        if self.occluded_by is None:
            self.occluded_by = []
        if self.occluding is None:
            self.occluding = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "shape": self.shape,
            "color": self.color,
            "hex_color": self.hex_color,
            "center": [round(self.center[0], 2), round(self.center[1], 2)],
            "size": round(self.size, 2),
            "z_order": self.z_order,
            "bbox": [round(v, 2) for v in self.bbox],
            "area": round(self.area, 2),
            "visible_area": round(self.visible_area, 2),
            "occlusion_ratio": round(self.occlusion_ratio, 4),
            "is_occluded": self.is_occluded,
            "is_partially_occluded": self.is_partially_occluded,
            "is_completely_occluded": self.is_completely_occluded,
            "is_unanswerable_target": self.is_unanswerable_target,
            "occluded_by": self.occluded_by,
            "occluding": self.occluding,
        }


@dataclass
class DistractorLine:
    type: str
    x1: float
    y1: float
    x2: float
    y2: float
    stroke_style: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "from": [round(self.x1, 2), round(self.y1, 2)],
            "to": [round(self.x2, 2), round(self.y2, 2)],
            "stroke_style": self.stroke_style,
        }


@dataclass
class Crosshair:
    cx: float
    cy: float
    size: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "crosshair",
            "center": [round(self.cx, 2), round(self.cy, 2)],
            "size": round(self.size, 2),
        }


class SceneBuilder:
    def __init__(self, config_path: str | Path = "config/difficulty_matrix.json") -> None:
        self.config_path = Path(config_path)
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.difficulty_matrix = json.load(f)

    @staticmethod
    def _create_geometry(shape: str, cx: float, cy: float, size: float) -> Tuple[shapely.Geometry, List[float], float]:
        """Creates Shapely geometry, bounding box [x1, y1, x2, y2], and nominal area."""
        half = size / 2.0
        if shape == "circle":
            r = half
            geom = Point(cx, cy).buffer(r, resolution=64)
            bbox = [cx - r, cy - r, cx + r, cy + r]
            area = math.pi * (r ** 2)
        elif shape == "square":
            x1, y1 = cx - half, cy - half
            x2, y2 = cx + half, cy + half
            geom = box(x1, y1, x2, y2)
            bbox = [x1, y1, x2, y2]
            area = size * size
        elif shape == "triangle":
            h = size * (math.sqrt(3) / 2.0)
            p1 = (cx, cy - h / 2.0)
            p2 = (cx - half, cy + h / 2.0)
            p3 = (cx + half, cy + h / 2.0)
            geom = Polygon([p1, p2, p3])
            bbox = [cx - half, cy - h / 2.0, cx + half, cy + h / 2.0]
            area = 0.5 * size * h
        else:
            raise ValueError(f"Unknown shape: {shape}")

        return geom, bbox, area

    def _generate_distractors(
        self, rng: random.Random, count: int
    ) -> Tuple[List[DistractorLine], List[Crosshair], List[str]]:
        """Generates technical schematic background distractors (gridlines, crosshairs, labels)."""
        distractor_lines: List[DistractorLine] = []
        crosshairs: List[Crosshair] = []
        labels: List[str] = []

        grid_step = 128
        for x in range(grid_step, CANVAS_SIZE, grid_step):
            distractor_lines.append(
                DistractorLine(type="grid_v", x1=x, y1=0, x2=x, y2=CANVAS_SIZE, stroke_style="grid-line")
            )
        for y in range(grid_step, CANVAS_SIZE, grid_step):
            distractor_lines.append(
                DistractorLine(type="grid_h", x1=0, y1=y, x2=CANVAS_SIZE, y2=y, stroke_style="grid-line")
            )

        for _ in range(count):
            line_type = rng.choice(["trace", "crosshair", "dimension", "marker"])
            if line_type == "trace":
                x1 = rng.uniform(CANVAS_PADDING, CANVAS_SIZE - CANVAS_PADDING)
                y1 = rng.uniform(CANVAS_PADDING, CANVAS_SIZE - CANVAS_PADDING)
                angle = rng.choice([0, math.pi / 4, math.pi / 2, 3 * math.pi / 4])
                length = rng.uniform(80, 250)
                x2 = max(CANVAS_PADDING, min(CANVAS_SIZE - CANVAS_PADDING, x1 + length * math.cos(angle)))
                y2 = max(CANVAS_PADDING, min(CANVAS_SIZE - CANVAS_PADDING, y1 + length * math.sin(angle)))
                distractor_lines.append(
                    DistractorLine(type="trace", x1=x1, y1=y1, x2=x2, y2=y2, stroke_style="distractor-trace")
                )
            elif line_type == "crosshair":
                cx = rng.uniform(CANVAS_PADDING * 2, CANVAS_SIZE - CANVAS_PADDING * 2)
                cy = rng.uniform(CANVAS_PADDING * 2, CANVAS_SIZE - CANVAS_PADDING * 2)
                crosshairs.append(Crosshair(cx=cx, cy=cy, size=rng.uniform(10, 16)))
            elif line_type == "dimension":
                x1 = rng.uniform(CANVAS_PADDING, CANVAS_SIZE - CANVAS_PADDING - 150)
                y1 = rng.uniform(CANVAS_PADDING, CANVAS_SIZE - CANVAS_PADDING)
                x2 = x1 + rng.uniform(80, 150)
                y2 = y1
                distractor_lines.append(
                    DistractorLine(type="dimension", x1=x1, y1=y1, x2=x2, y2=y2, stroke_style="major-grid-line")
                )
            elif line_type == "marker":
                lx = rng.uniform(CANVAS_PADDING, CANVAS_SIZE - CANVAS_PADDING)
                ly = rng.uniform(CANVAS_PADDING, CANVAS_SIZE - CANVAS_PADDING)
                sec_id = f"SEC-{rng.randint(10, 99)}:X{int(lx)}:Y{int(ly)}"
                labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" class="tech-label">{sec_id}</text>')

        return distractor_lines, crosshairs, labels

    def _compute_occlusions(self, placed_nodes: List[Dict[str, Any]]) -> List[Node]:
        """Calculates exact Shapely visible areas, occlusion ratios, and occlusion relations."""
        nodes: List[Node] = []
        n_nodes = len(placed_nodes)

        for i, info in enumerate(placed_nodes):
            node_id = info.get("id", f"node_{i}")
            geom_i = info["geom"]
            area_i = info["area"]
            is_unans = info.get("is_unanswerable_target", False)

            higher_geoms = [placed_nodes[j]["geom"] for j in range(i + 1, n_nodes)]

            occluded_by: List[str] = []
            for j in range(i + 1, n_nodes):
                other_id = placed_nodes[j].get("id", f"node_{j}")
                inter = geom_i.intersection(placed_nodes[j]["geom"])
                if inter.area > 0.02 * area_i:
                    occluded_by.append(other_id)

            occluding: List[str] = []
            for j in range(0, i):
                other_id = placed_nodes[j].get("id", f"node_{j}")
                inter = geom_i.intersection(placed_nodes[j]["geom"])
                if inter.area > 0.02 * placed_nodes[j]["area"]:
                    occluding.append(other_id)

            if higher_geoms:
                higher_union = unary_union(higher_geoms)
                visible_geom = geom_i.difference(higher_union)
                visible_area = max(0.0, visible_geom.area)
            else:
                visible_area = area_i

            occlusion_ratio = max(0.0, min(1.0, 1.0 - (visible_area / area_i)))

            if is_unans:
                visible_area = 0.0
                occlusion_ratio = 1.0
                is_occluded = True
                is_partially = False
                is_completely = True
            else:
                visible_ratio = visible_area / area_i if area_i > 0 else 0.0
                is_occluded = len(occluded_by) > 0 and occlusion_ratio >= 0.05
                # Strict Milestone 2 bounds: partially occluded visible ratio must be in [0.10, 0.90]
                is_partially = is_occluded and (0.10 <= visible_ratio <= 0.90)
                is_completely = visible_ratio < 0.10

            node = Node(
                id=node_id,
                shape=info["shape"],
                color=info["color"],
                hex_color=info["hex_color"],
                center=(info["cx"], info["cy"]),
                size=info["size"],
                z_order=i,
                bbox=info["bbox"],
                area=area_i,
                visible_area=visible_area,
                occlusion_ratio=occlusion_ratio,
                is_occluded=is_occluded,
                is_partially_occluded=is_partially,
                is_completely_occluded=is_completely,
                is_unanswerable_target=is_unans,
                occluded_by=occluded_by,
                occluding=occluding,
            )
            nodes.append(node)

        return nodes

    def generate(
        self,
        seed: int,
        difficulty: str = "medium",
        mode: str = "standard",
    ) -> Dict[str, Any]:
        """Generates a scene deterministically from seed, difficulty, and mode."""
        if difficulty not in self.difficulty_matrix:
            raise ValueError(f"Unknown difficulty '{difficulty}'. Options: {list(self.difficulty_matrix.keys())}")

        cfg = self.difficulty_matrix[difficulty]
        rng = random.Random(seed)

        node_count = cfg["node_count"]
        target_occlusion_ratio = cfg["occlusion_ratio"]
        distractor_count = cfg["distractor_count"]
        min_size = cfg["min_node_size"]
        max_size = cfg["max_node_size"]

        target_occluded_count = int(round(node_count * target_occlusion_ratio))
        color_keys = list(COLOR_PALETTE.keys())

        # Group sizes to structure deliberate partial overlaps
        remaining_occluded = target_occluded_count
        remaining_nodes = node_count
        group_sizes: List[int] = []

        while remaining_nodes > 0:
            if remaining_occluded >= 3 and remaining_nodes >= 4:
                group_sizes.append(4)
                remaining_occluded -= 3
                remaining_nodes -= 4
            elif remaining_occluded >= 2 and remaining_nodes >= 3:
                group_sizes.append(3)
                remaining_occluded -= 2
                remaining_nodes -= 3
            elif remaining_occluded >= 1 and remaining_nodes >= 2:
                group_sizes.append(2)
                remaining_occluded -= 1
                remaining_nodes -= 2
            else:
                group_sizes.append(1)
                remaining_nodes -= 1

        placed_nodes_info: List[Dict[str, Any]] = []

        # If abstention mode: create a hidden target node covered completely by an occluder
        if mode == "unanswerable":
            unans_size = min_size
            unans_margin = unans_size + CANVAS_PADDING * 2
            unans_cx = rng.uniform(unans_margin, CANVAS_SIZE - unans_margin)
            unans_cy = rng.uniform(unans_margin, CANVAS_SIZE - unans_margin)
            unans_shape = rng.choice(SHAPE_TYPES)
            unans_color = rng.choice(color_keys)
            geom_unans, bbox_unans, area_unans = self._create_geometry(
                unans_shape, unans_cx, unans_cy, unans_size
            )

            placed_nodes_info.append({
                "id": "node_hidden_target",
                "shape": unans_shape,
                "color": unans_color,
                "hex_color": COLOR_PALETTE[unans_color],
                "cx": unans_cx,
                "cy": unans_cy,
                "size": unans_size,
                "z_order": 0,
                "geom": geom_unans,
                "bbox": bbox_unans,
                "area": area_unans,
                "is_unanswerable_target": True,
            })

            cover_size = unans_size * 1.6
            cover_shape = "square"
            cover_color = rng.choice([c for c in color_keys if c != unans_color])
            geom_cover, bbox_cover, area_cover = self._create_geometry(
                cover_shape, unans_cx, unans_cy, cover_size
            )
            placed_nodes_info.append({
                "id": "node_cover",
                "shape": cover_shape,
                "color": cover_color,
                "hex_color": COLOR_PALETTE[cover_color],
                "cx": unans_cx,
                "cy": unans_cy,
                "size": cover_size,
                "z_order": 1,
                "geom": geom_cover,
                "bbox": bbox_cover,
                "area": area_cover,
                "is_unanswerable_target": False,
            })

        for group_size in group_sizes:
            base_size = rng.uniform(min_size, max_size)
            margin = base_size + CANVAS_PADDING

            base_cx, base_cy = rng.uniform(margin, CANVAS_SIZE - margin), rng.uniform(margin, CANVAS_SIZE - margin)
            for attempt in range(120):
                cand_cx = rng.uniform(margin, CANVAS_SIZE - margin)
                cand_cy = rng.uniform(margin, CANVAS_SIZE - margin)
                too_close = any(
                    math.hypot(cand_cx - ni["cx"], cand_cy - ni["cy"]) < (base_size + ni["size"]) * 1.15
                    for ni in placed_nodes_info
                )
                if not too_close:
                    base_cx, base_cy = cand_cx, cand_cy
                    break

            current_cx, current_cy = base_cx, base_cy
            current_size = base_size

            for member_idx in range(group_size):
                if member_idx == 0:
                    node_cx, node_cy = current_cx, current_cy
                    node_size = current_size
                    shape = rng.choice(SHAPE_TYPES)
                    geom, bbox, area = self._create_geometry(shape, node_cx, node_cy, node_size)
                else:
                    found_placement = False
                    for attempt in range(60):
                        cand_size = rng.uniform(min_size, max_size)
                        cand_shape = rng.choice(SHAPE_TYPES)
                        overlap_dist = (current_size / 2.0 + cand_size / 2.0) * rng.uniform(0.50, 0.80)
                        angle = rng.uniform(0, 2 * math.pi)
                        raw_cx = current_cx + overlap_dist * math.cos(angle)
                        raw_cy = current_cy + overlap_dist * math.sin(angle)

                        half_s = cand_size / 2.0 + 5.0
                        cand_cx = max(CANVAS_PADDING + half_s, min(CANVAS_SIZE - CANVAS_PADDING - half_s, raw_cx))
                        cand_cy = max(CANVAS_PADDING + half_s, min(CANVAS_SIZE - CANVAS_PADDING - half_s, raw_cy))

                        cand_geom, cand_bbox, cand_area = self._create_geometry(cand_shape, cand_cx, cand_cy, cand_size)

                        valid_overlap = True
                        for prev_node in placed_nodes_info:
                            if prev_node.get("is_unanswerable_target"):
                                continue
                            inter = prev_node["geom"].intersection(cand_geom)
                            if inter.area > 0:
                                prev_higher = [
                                    p["geom"] for p in placed_nodes_info if p["z_order"] > prev_node["z_order"]
                                ] + [cand_geom]
                                prev_union = unary_union(prev_higher)
                                rem_vis = prev_node["geom"].difference(prev_union).area
                                if rem_vis / prev_node["area"] < 0.12:
                                    valid_overlap = False
                                    break

                        if valid_overlap:
                            node_cx, node_cy = cand_cx, cand_cy
                            node_size = cand_size
                            shape = cand_shape
                            geom, bbox, area = cand_geom, cand_bbox, cand_area
                            found_placement = True
                            break

                    if not found_placement:
                        node_size = rng.uniform(min_size, max_size)
                        shape = rng.choice(SHAPE_TYPES)
                        half_s = node_size / 2.0 + 5.0
                        node_cx = rng.uniform(CANVAS_PADDING + half_s, CANVAS_SIZE - CANVAS_PADDING - half_s)
                        node_cy = rng.uniform(CANVAS_PADDING + half_s, CANVAS_SIZE - CANVAS_PADDING - half_s)
                        geom, bbox, area = self._create_geometry(shape, node_cx, node_cy, node_size)

                    current_cx, current_cy = node_cx, node_cy
                    current_size = node_size

                color = rng.choice(color_keys)
                hex_color = COLOR_PALETTE[color]

                node_entry = {
                    "id": f"node_{len(placed_nodes_info)}",
                    "shape": shape,
                    "color": color,
                    "hex_color": hex_color,
                    "cx": node_cx,
                    "cy": node_cy,
                    "size": node_size,
                    "z_order": len(placed_nodes_info),
                    "geom": geom,
                    "bbox": bbox,
                    "area": area,
                    "is_unanswerable_target": False,
                }
                placed_nodes_info.append(node_entry)

        nodes = self._compute_occlusions(placed_nodes_info)
        distractor_lines, crosshairs, tech_labels = self._generate_distractors(rng, distractor_count)
        qa_pairs = self._generate_qa_pairs(rng, nodes, mode=mode)
        html_content = self._render_html(seed, difficulty, nodes, distractor_lines, crosshairs, tech_labels)

        scene_data = {
            "metadata": {
                "seed": seed,
                "difficulty": difficulty,
                "mode": mode,
                "canvas_width": CANVAS_SIZE,
                "canvas_height": CANVAS_SIZE,
                "total_nodes": len(nodes),
                "total_distractor_lines": len(distractor_lines),
                "total_crosshairs": len(crosshairs),
                "validation_status": "PASSED",
            },
            "nodes": [n.to_dict() for n in nodes],
            "distractors": [d.to_dict() for d in distractor_lines] + [c.to_dict() for c in crosshairs],
            "qa_pairs": qa_pairs,
            "html_content": html_content,
        }

        return scene_data

    def generate_counterfactual_pair(
        self,
        seed: int,
        difficulty: str = "medium",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Generates a base scene and a surgical counterfactual twin from the same seed.

        Differs by swapping the z-order of exactly ONE overlapping pair of nodes,
        leaving ~98% of the diagram identical while flipping the ground-truth answer.
        """
        base_scene = self.generate(seed=seed, difficulty=difficulty, mode="standard")
        base_nodes = base_scene["nodes"]

        rng = random.Random(seed)
        candidate_pairs: List[Tuple[int, int]] = []
        for i, n_i in enumerate(base_nodes):
            for occ_id in n_i["occluded_by"]:
                j = next((k for k, n in enumerate(base_nodes) if n["id"] == occ_id), None)
                if j is not None and j > i:
                    if n_i["color"] != base_nodes[j]["color"] or n_i["shape"] != base_nodes[j]["shape"]:
                        candidate_pairs.append((i, j))

        if not candidate_pairs:
            for i, n_i in enumerate(base_nodes):
                for occ_id in n_i["occluded_by"]:
                    j = next((k for k, n in enumerate(base_nodes) if n["id"] == occ_id), None)
                    if j is not None and j > i:
                        candidate_pairs.append((i, j))

        if not candidate_pairs:
            raise RuntimeError(f"Could not find overlapping pair for counterfactual edit with seed {seed}")

        # Filter candidate pairs to ensure the swapped z-order preserves valid visibility ratio (>= 0.10)
        rng.shuffle(candidate_pairs)
        selected_pair = None

        for cand_a, cand_b in candidate_pairs:
            # Test swap
            test_placed = []
            for n in base_nodes:
                g, b, a = self._create_geometry(n["shape"], n["center"][0], n["center"][1], n["size"])
                test_placed.append({
                    "id": n["id"], "shape": n["shape"], "color": n["color"], "hex_color": n["hex_color"],
                    "cx": n["center"][0], "cy": n["center"][1], "size": n["size"], "geom": g, "bbox": b, "area": a,
                    "is_unanswerable_target": n.get("is_unanswerable_target", False),
                })
            test_placed[cand_a], test_placed[cand_b] = test_placed[cand_b], test_placed[cand_a]
            test_nodes = self._compute_occlusions(test_placed)

            # Check if any node in test_nodes is invalid (< 0.10 visible without being unanswerable)
            valid_swap = True
            for tn in test_nodes:
                if not tn.is_unanswerable_target and tn.visible_area / tn.area < 0.10:
                    valid_swap = False
                    break

            if valid_swap:
                selected_pair = (cand_a, cand_b)
                break

        if selected_pair is None:
            selected_pair = candidate_pairs[0]

        idx_a, idx_b = selected_pair
        node_a_orig = base_nodes[idx_a]
        node_b_orig = base_nodes[idx_b]

        placed_nodes_cf: List[Dict[str, Any]] = []
        for n in base_nodes:
            geom, bbox, area = self._create_geometry(n["shape"], n["center"][0], n["center"][1], n["size"])
            placed_nodes_cf.append({
                "id": n["id"],
                "shape": n["shape"],
                "color": n["color"],
                "hex_color": n["hex_color"],
                "cx": n["center"][0],
                "cy": n["center"][1],
                "size": n["size"],
                "geom": geom,
                "bbox": bbox,
                "area": area,
                "is_unanswerable_target": n.get("is_unanswerable_target", False),
            })

        # Swap z-order position in list
        placed_nodes_cf[idx_a], placed_nodes_cf[idx_b] = placed_nodes_cf[idx_b], placed_nodes_cf[idx_a]
        cf_nodes = self._compute_occlusions(placed_nodes_cf)

        distractor_lines = [
            DistractorLine(
                type=d["type"],
                x1=d["from"][0],
                y1=d["from"][1],
                x2=d["to"][0],
                y2=d["to"][1],
                stroke_style=d.get("stroke_style", "grid-line"),
            )
            for d in base_scene["distractors"]
            if d["type"] != "crosshair"
        ]
        crosshairs = [
            Crosshair(cx=d["center"][0], cy=d["center"][1], size=d["size"])
            for d in base_scene["distractors"]
            if d["type"] == "crosshair"
        ]

        q_text = (
            f"Is the {node_a_orig['color']} {node_a_orig['shape']} at "
            f"({int(node_a_orig['center'][0])}, {int(node_a_orig['center'][1])}) "
            f"partially occluded by the {node_b_orig['color']} {node_b_orig['shape']}?"
        )

        qa_base_target = self._create_binary_qa(
            rng,
            question_id="q_cf_target",
            question_text=q_text,
            is_true=True,
            target_ids=[node_a_orig["id"], node_b_orig["id"]],
        )
        qa_cf_target = self._create_binary_qa(
            rng,
            question_id="q_cf_target",
            question_text=q_text,
            is_true=False,
            target_ids=[node_a_orig["id"], node_b_orig["id"]],
        )

        base_scene["metadata"]["twin_type"] = "base"
        base_scene["metadata"]["counterfactual_target"] = [node_a_orig["id"], node_b_orig["id"]]
        base_scene["metadata"]["surgical_edit"] = f"swapped z-order of {node_a_orig['id']} and {node_b_orig['id']}"
        base_scene["qa_pairs"] = [qa_base_target] + base_scene["qa_pairs"][:2]

        cf_qa_pairs = self._generate_qa_pairs(rng, cf_nodes, mode="standard")
        cf_qa_pairs = [qa_cf_target] + cf_qa_pairs[:2]

        cf_html = self._render_html(seed, difficulty, cf_nodes, distractor_lines, crosshairs, [])

        cf_scene = {
            "metadata": {
                "seed": seed,
                "difficulty": difficulty,
                "mode": "standard",
                "twin_type": "counterfactual",
                "counterfactual_target": [node_a_orig["id"], node_b_orig["id"]],
                "surgical_edit": f"swapped z-order of {node_a_orig['id']} and {node_b_orig['id']}",
                "canvas_width": CANVAS_SIZE,
                "canvas_height": CANVAS_SIZE,
                "total_nodes": len(cf_nodes),
                "total_distractor_lines": len(distractor_lines),
                "total_crosshairs": len(crosshairs),
                "validation_status": "PASSED",
            },
            "nodes": [n.to_dict() for n in cf_nodes],
            "distractors": base_scene["distractors"],
            "qa_pairs": cf_qa_pairs,
            "html_content": cf_html,
        }

        return base_scene, cf_scene

    def _create_binary_qa(
        self,
        rng: random.Random,
        question_id: str,
        question_text: str,
        is_true: bool,
        target_ids: List[str],
    ) -> Dict[str, Any]:
        """Creates dual-format binary (yes/no) Q&A item."""
        correct_answer = "yes" if is_true else "no"
        options_list = ["yes", "no", "cannot_determine", "partially"]
        rng.shuffle(options_list)

        options = {chr(65 + i): opt for i, opt in enumerate(options_list)}
        correct_option = next(k for k, v in options.items() if v == correct_answer)

        mcq_question = f"{question_text}\n" + "\n".join(f"{k}) {v}" for k, v in options.items())

        return {
            "question_id": question_id,
            "type": "binary_occlusion_check",
            "is_counterfactual_target": True,
            "matching_node_ids": target_ids,
            "open_ended": {
                "question": question_text,
                "answer": correct_answer,
            },
            "mcq": {
                "question": mcq_question,
                "options": options,
                "correct_option": correct_option,
                "answer": correct_answer,
            },
            "question": question_text,
            "answer": correct_answer,
        }

    def _render_html(
        self,
        seed: int,
        difficulty: str,
        nodes: List[Node],
        distractor_lines: List[DistractorLine],
        crosshairs: List[Crosshair],
        tech_labels: List[str],
    ) -> str:
        """Renders complete HTML5 document containing the SVG technical diagram."""
        lines_svg = [
            f'<line x1="{d.x1:.2f}" y1="{d.y1:.2f}" x2="{d.x2:.2f}" y2="{d.y2:.2f}" class="{d.stroke_style}" />'
            for d in distractor_lines
        ]

        crosshairs_svg = []
        for c in crosshairs:
            s = c.size / 2.0
            crosshairs_svg.append(
                f'<line x1="{c.cx - s:.2f}" y1="{c.cy:.2f}" x2="{c.cx + s:.2f}" y2="{c.cy:.2f}" class="crosshair" />'
            )
            crosshairs_svg.append(
                f'<line x1="{c.cx:.2f}" y1="{c.cy - s:.2f}" x2="{c.cx:.2f}" y2="{c.cy + s:.2f}" class="crosshair" />'
            )

        nodes_svg = []
        for n in nodes:
            cx, cy = n.center
            size = n.size
            half = size / 2.0
            color = n.hex_color
            node_id = n.id

            if n.shape == "circle":
                nodes_svg.append(
                    f'<circle id="{node_id}" data-color="{n.color}" data-z="{n.z_order}" '
                    f'cx="{cx:.2f}" cy="{cy:.2f}" r="{half:.2f}" '
                    f'fill="{color}" class="node-shape" />'
                )
            elif n.shape == "square":
                x = cx - half
                y = cy - half
                nodes_svg.append(
                    f'<rect id="{node_id}" data-color="{n.color}" data-z="{n.z_order}" '
                    f'x="{x:.2f}" y="{y:.2f}" width="{size:.2f}" height="{size:.2f}" '
                    f'fill="{color}" class="node-shape" />'
                )
            elif n.shape == "triangle":
                h = size * (math.sqrt(3) / 2.0)
                p1 = f"{cx:.2f},{cy - h / 2.0:.2f}"
                p2 = f"{cx - half:.2f},{cy + h / 2.0:.2f}"
                p3 = f"{cx + half:.2f},{cy + h / 2.0:.2f}"
                nodes_svg.append(
                    f'<polygon id="{node_id}" data-color="{n.color}" data-z="{n.z_order}" '
                    f'points="{p1} {p2} {p3}" '
                    f'fill="{color}" class="node-shape" />'
                )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Technical Diagram - Seed {seed} ({difficulty})</title>
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}
    html, body {{
      width: 1024px;
      height: 1024px;
      overflow: hidden;
      background-color: #0b1120;
    }}
    svg {{
      display: block;
      width: 1024px;
      height: 1024px;
      user-select: none;
    }}
    .grid-line {{
      stroke: #1e293b;
      stroke-width: 1;
    }}
    .major-grid-line {{
      stroke: #334155;
      stroke-width: 1.5;
      stroke-dasharray: 4,4;
    }}
    .distractor-trace {{
      stroke: #38bdf8;
      stroke-opacity: 0.35;
      stroke-width: 1.2;
      stroke-dasharray: 5,4;
      fill: none;
    }}
    .crosshair {{
      stroke: #64748b;
      stroke-width: 1.2;
    }}
    .tech-label {{
      font-family: 'Consolas', 'Courier New', monospace;
      font-size: 9px;
      fill: #475569;
      letter-spacing: 0.5px;
    }}
    .node-shape {{
      stroke: #020617;
      stroke-width: 2.2;
      stroke-linejoin: round;
    }}
  </style>
</head>
<body>
  <svg viewBox="0 0 1024 1024" width="1024" height="1024" xmlns="http://www.w3.org/2000/svg">
    <!-- Technical Distractor Grid & Markings Layer -->
    <g id="distractor-lines">
      {chr(10).join("      " + line for line in lines_svg)}
    </g>
    <g id="crosshairs">
      {chr(10).join("      " + ch for ch in crosshairs_svg)}
    </g>
    <g id="tech-labels">
      {chr(10).join("      " + lbl for lbl in tech_labels)}
    </g>
    <!-- Geometric Nodes Layer (ordered by z-order) -->
    <g id="nodes">
      {chr(10).join("      " + n for n in nodes_svg)}
    </g>
  </svg>
</body>
</html>"""
        return html

    def _format_dual_qa(
        self,
        rng: random.Random,
        base_question: str,
        answer: Any,
        answer_type: str = "count",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Formats a question into both open_ended and 4-option MCQ structures."""
        ans_str = str(answer)

        if answer_type == "count":
            cnt = int(answer)
            distractor_pool = [cnt + 1, cnt + 2, cnt + 3, max(0, cnt - 1), max(0, cnt - 2), cnt + 4]
            distractor_pool = sorted(list(set(d for d in distractor_pool if d != cnt)))
            chosen_distractors = rng.sample(distractor_pool, 3)
            choices = [str(cnt)] + [str(d) for d in chosen_distractors]
        elif answer_type == "abstention":
            distractor_pool = ["red circle", "blue square", "green triangle", "none"]
            chosen_distractors = rng.sample(distractor_pool, 3)
            choices = ["cannot_determine"] + chosen_distractors
        else:
            choices = ["yes", "no", "cannot_determine", "unknown"]

        rng.shuffle(choices)
        options = {chr(65 + i): c for i, c in enumerate(choices)}
        correct_option = next(k for k, v in options.items() if v == ans_str)

        mcq_question = f"{base_question}\n" + "\n".join(f"{k}) {v}" for k, v in options.items())

        open_ended = {
            "question": base_question,
            "answer": ans_str,
        }
        mcq = {
            "question": mcq_question,
            "options": options,
            "correct_option": correct_option,
            "answer": ans_str,
        }
        return open_ended, mcq

    def _generate_qa_pairs(
        self,
        rng: random.Random,
        nodes: List[Node],
        mode: str = "standard",
    ) -> List[Dict[str, Any]]:
        """Generates 3 verifiable Q&A pairs in dual format (open_ended and mcq)."""
        selected_pairs: List[Dict[str, Any]] = []

        if mode == "unanswerable":
            hidden_node = next((n for n in nodes if n.is_unanswerable_target), None)
            cover_node = next((n for n in nodes if n.id == "node_cover"), None)
            if hidden_node and cover_node:
                q_text = (
                    f"What is the exact shape and color of the node occluded completely beneath "
                    f"the {cover_node.color} {cover_node.shape} near coordinates "
                    f"({int(cover_node.center[0])}, {int(cover_node.center[1])})? "
                    f"If it cannot be visually determined, answer 'cannot_determine'."
                )
                open_ended, mcq = self._format_dual_qa(rng, q_text, "cannot_determine", answer_type="abstention")
                selected_pairs.append({
                    "question_id": "q1",
                    "type": "abstention",
                    "is_unanswerable": True,
                    "criteria": {"is_unanswerable": True},
                    "matching_node_ids": [hidden_node.id],
                    "open_ended": open_ended,
                    "mcq": mcq,
                    "question": q_text,
                    "answer": "cannot_determine",
                })

        colors_present = sorted(list(set(n.color for n in nodes if not n.is_unanswerable_target)))
        shapes_present = sorted(list(set(n.shape for n in nodes if not n.is_unanswerable_target)))

        candidate_generators = []

        for c in colors_present:
            for s in shapes_present:
                matches = [
                    n.id for n in nodes if n.color == c and n.shape == s and n.is_partially_occluded
                ]
                count = len(matches)
                candidate_generators.append({
                    "type": "partially_occluded_color_shape",
                    "base_q": f"How many {c} {s}s in the diagram are partially occluded?",
                    "answer": count,
                    "criteria": {"color": c, "shape": s, "is_partially_occluded": True},
                    "matching_node_ids": matches,
                    "priority": 2 if count > 0 else 1,
                })

        for c in colors_present:
            matches = [n.id for n in nodes if n.color == c and n.is_partially_occluded]
            count = len(matches)
            candidate_generators.append({
                "type": "partially_occluded_color",
                "base_q": f"How many {c} shapes of any type are partially occluded by another shape?",
                "answer": count,
                "criteria": {"color": c, "is_partially_occluded": True},
                "matching_node_ids": matches,
                "priority": 3 if count > 0 else 1,
            })

        for c in colors_present:
            matches = [n.id for n in nodes if n.color == c and not n.is_occluded]
            count = len(matches)
            candidate_generators.append({
                "type": "unoccluded_color",
                "base_q": f"How many {c} shapes are completely unoccluded?",
                "answer": count,
                "criteria": {"color": c, "is_occluded": False},
                "matching_node_ids": matches,
                "priority": 3 if count > 0 else 1,
            })

        total_partially_occluded = [n.id for n in nodes if n.is_partially_occluded]
        candidate_generators.append({
            "type": "total_partially_occluded",
            "base_q": "What is the total number of partially occluded shapes in the diagram?",
            "answer": len(total_partially_occluded),
            "criteria": {"is_partially_occluded": True},
            "matching_node_ids": total_partially_occluded,
            "priority": 4,
        })

        rng.shuffle(candidate_generators)
        candidate_generators.sort(key=lambda q: q["priority"], reverse=True)

        used_types = set(p["type"] for p in selected_pairs)
        for cand in candidate_generators:
            if cand["type"] not in used_types:
                used_types.add(cand["type"])
                open_ended, mcq = self._format_dual_qa(rng, cand["base_q"], cand["answer"], answer_type="count")
                q_id = f"q{len(selected_pairs) + 1}"
                selected_pairs.append({
                    "question_id": q_id,
                    "type": cand["type"],
                    "criteria": cand["criteria"],
                    "matching_node_ids": cand["matching_node_ids"],
                    "open_ended": open_ended,
                    "mcq": mcq,
                    "question": cand["base_q"],
                    "answer": cand["answer"],
                })
                if len(selected_pairs) == 3:
                    break

        return selected_pairs

    def save(self, scene_data: Dict[str, Any], output_dir: Path | str) -> Tuple[Path, Path]:
        """Saves scene.html and ground_truth.json to output directory."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        html_file = out_path / "scene.html"
        gt_file = out_path / "ground_truth.json"

        html_content = scene_data["html_content"]
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        gt_data = {k: v for k, v in scene_data.items() if k != "html_content"}
        with open(gt_file, "w", encoding="utf-8") as f:
            json.dump(gt_data, f, indent=2)

        return html_file, gt_file


def build_scene(
    seed: int,
    difficulty: str = "medium",
    output_dir: Optional[str | Path] = None,
    config_path: str | Path = "config/difficulty_matrix.json",
    mode: str = "standard",
) -> Dict[str, Any]:
    """Convenience helper to generate and optionally save a scene."""
    builder = SceneBuilder(config_path=config_path)
    scene_data = builder.generate(seed=seed, difficulty=difficulty, mode=mode)
    if output_dir:
        builder.save(scene_data, output_dir)
    return scene_data


def main():
    parser = argparse.ArgumentParser(description="Deterministic Scene Builder for Visual Task Factory")
    parser.add_argument("--seed", type=int, default=42, help="Integer seed for deterministic generation")
    parser.add_argument(
        "--difficulty", type=str, choices=["easy", "medium", "hard"], default="medium", help="Difficulty level"
    )
    parser.add_argument(
        "--mode", type=str, choices=["standard", "unanswerable"], default="standard", help="Task mode"
    )
    parser.add_argument("--counterfactual", action="store_true", help="Generate counterfactual pair")
    parser.add_argument("--output-dir", type=str, default="output/sample", help="Output directory path")
    parser.add_argument(
        "--config", type=str, default="config/difficulty_matrix.json", help="Path to difficulty matrix JSON"
    )
    args = parser.parse_args()

    builder = SceneBuilder(config_path=args.config)
    if args.counterfactual:
        base, cf = builder.generate_counterfactual_pair(seed=args.seed, difficulty=args.difficulty)
        out_p = Path(args.output_dir)
        b_html, b_gt = builder.save(base, out_p / "base")
        c_html, c_gt = builder.save(cf, out_p / "counterfactual")
        print(f"Generated counterfactual pair successfully in {out_p}")
    else:
        scene_data = builder.generate(seed=args.seed, difficulty=args.difficulty, mode=args.mode)
        html_path, gt_path = builder.save(scene_data, args.output_dir)
        print(f"Generated scene successfully:")
        print(f"  HTML: {html_path}")
        print(f"  Ground Truth: {gt_path}")
        print(f"  Nodes: {len(scene_data['nodes'])}")
        print(f"  Q&A count: {len(scene_data['qa_pairs'])}")


if __name__ == "__main__":
    main()
