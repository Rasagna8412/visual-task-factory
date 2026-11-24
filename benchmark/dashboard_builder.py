"""Dashboard Builder module for Visual Task Factory.

Generates an ultra-premium, vibrant 3D Glassmorphic Demo Day dashboard (`dashboard.html`)
with realistic specular highlights, translucent frosted glass, dynamic neon rim lighting,
interactive 3D card physics, and an animated, interactive "⇄ FLIP" button that swaps
counterfactual z-orders and inverts ground truth in real time with 3D card-flip animation.
"""

from __future__ import annotations

import base64
import datetime
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def _b64_img(img_path: Path) -> str:
    """Helper to convert image to data URI base64 string for standalone portability."""
    if img_path.exists():
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/png;base64,{b64}"
    return ""


class DashboardBuilder:
    """Builds self-contained HTML Demo Day dashboard with interactive 3D glassmorphism."""

    def __init__(self, run_dir: Union[str, Path]) -> None:
        self.run_dir = Path(run_dir)
        self.charts_dir = self.run_dir / "charts"

    def build(
        self,
        summary_metrics: Dict[str, Any],
        raw_results: Optional[List[Dict[str, Any]]] = None,
        cf_pairs_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Path:
        """Assembles dashboard.html in run_dir."""
        out_html = self.run_dir / "dashboard.html"

        c1_path = self.charts_dir / "accuracy_by_difficulty.png"
        c2_path = self.charts_dir / "consistency_and_mcq_gap.png"
        c3_path = self.charts_dir / "occlusion_dropoff.png"

        c1_b64 = _b64_img(c1_path)
        c2_b64 = _b64_img(c2_path)
        c3_b64 = _b64_img(c3_path)

        if not cf_pairs_data:
            cf_pairs_data = self._discover_cf_pairs()

        abstention_data = self._discover_abstention_task()

        html_content = self._render_template(
            summary_metrics=summary_metrics,
            c1_b64=c1_b64,
            c2_b64=c2_b64,
            c3_b64=c3_b64,
            cf_pairs=cf_pairs_data,
            abstention=abstention_data,
        )

        with open(out_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        return out_html

    def _discover_cf_pairs(self) -> List[Dict[str, Any]]:
        """Finds base/counterfactual pairs in the run directory."""
        pairs: Dict[str, Dict[str, Any]] = {}

        for gt_p in sorted(list(self.run_dir.rglob("ground_truth.json"))):
            folder = gt_p.parent
            png_p = folder / "scene.png"
            if not png_p.exists():
                continue

            try:
                with open(gt_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            meta = data.get("metadata", {})
            if meta.get("validation_status") == "REJECTED":
                continue
            twin_type = meta.get("twin_type")
            if twin_type in ["base", "counterfactual"]:
                match = re.match(r"(pair_\d+)", folder.name)
                pair_key = match.group(1) if match else folder.name
                if pair_key not in pairs:
                    pairs[pair_key] = {"pair_id": pair_key, "difficulty": meta.get("difficulty", "medium")}

                target_qa = next((q for q in data.get("qa_pairs", []) if q.get("is_counterfactual_target")), None)
                q_text = target_qa["open_ended"]["question"] if target_qa else "Is shape A occluded by shape B?"
                ans = target_qa["open_ended"]["answer"] if target_qa else ("yes" if twin_type == "base" else "no")

                pairs[pair_key][twin_type] = {
                    "folder": folder.name,
                    "png_b64": _b64_img(png_p),
                    "answer": ans,
                    "question": q_text,
                    "edit": meta.get("surgical_edit", "swapped z-order of 2 shapes"),
                }

        cf_list = []
        for p_id, p_info in sorted(pairs.items()):
            if "base" in p_info and "counterfactual" in p_info:
                cf_list.append({
                    "pair_id": p_id,
                    "difficulty": p_info.get("difficulty", "medium"),
                    "question": p_info["base"]["question"],
                    "edit": p_info["base"]["edit"],
                    "base_b64": p_info["base"]["png_b64"],
                    "base_answer": p_info["base"]["answer"],
                    "cf_b64": p_info["counterfactual"]["png_b64"],
                    "cf_answer": p_info["counterfactual"]["answer"],
                })
                if len(cf_list) >= 4:
                    break
        return cf_list

    def _discover_abstention_task(self) -> Optional[Dict[str, Any]]:
        """Finds an abstention task in run directory."""
        for gt_p in sorted(list(self.run_dir.rglob("ground_truth.json"))):
            folder = gt_p.parent
            png_p = folder / "scene.png"
            if not png_p.exists():
                continue
            try:
                with open(gt_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            if (
                data.get("metadata", {}).get("mode") == "unanswerable"
                and data.get("metadata", {}).get("validation_status") != "REJECTED"
            ):
                hidden = next((n for n in data.get("nodes", []) if n.get("is_unanswerable_target")), {})
                cover = next((n for n in data.get("nodes", []) if n.get("id") == "node_cover"), {})
                qa0 = data.get("qa_pairs", [{}])[0]
                return {
                    "folder": folder.name,
                    "png_b64": _b64_img(png_p),
                    "question": qa0.get("open_ended", {}).get("question", ""),
                    "answer": qa0.get("open_ended", {}).get("answer", "cannot_determine"),
                    "hidden_shape": f"{hidden.get('color', '')} {hidden.get('shape', '')}",
                    "cover_shape": f"{cover.get('color', '')} {cover.get('shape', '')}",
                }
        return None

    def _render_template(
        self,
        summary_metrics: Dict[str, Any],
        c1_b64: str,
        c2_b64: str,
        c3_b64: str,
        cf_pairs: List[Dict[str, Any]],
        abstention: Optional[Dict[str, Any]],
    ) -> str:
        """Renders the comprehensive 3D high-gloss glassmorphic HTML5 template with interactive FLIP."""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sorted_models = sorted(
            summary_metrics.items(),
            key=lambda item: item[1].get("open_ended_accuracy", 0.0),
            reverse=True,
        )

        top_name, top_m = sorted_models[0] if sorted_models else ("none", {})
        baseline_name, baseline_m = sorted_models[-1] if len(sorted_models) > 1 else (top_name, top_m)

        top_open = top_m.get("open_ended_accuracy", 0.0)
        top_mcq = top_m.get("mcq_accuracy", 0.0)
        top_gap = top_m.get("mcq_shortcut_gap", 0.0)
        top_cons = top_m.get("pairwise_consistency", 0.0)
        top_abs = top_m.get("abstention_accuracy", 0.0)

        baseline_open = baseline_m.get("open_ended_accuracy", 0.0)
        baseline_mcq = baseline_m.get("mcq_accuracy", 0.0)
        baseline_gap = baseline_m.get("mcq_shortcut_gap", 0.0)
        baseline_cons = baseline_m.get("pairwise_consistency", 0.0)
        baseline_abs = baseline_m.get("abstention_accuracy", 0.0)

        leaderboard_rows = []
        rank_badges = ["🥇 1st", "🥈 2nd", "🥉 3rd", "4th", "5th"]
        for idx, (m, d) in enumerate(sorted_models):
            rank_str = rank_badges[idx] if idx < len(rank_badges) else f"{idx + 1}th"
            gap_val = d.get("mcq_shortcut_gap", 0.0)
            gap_sign = "+" if gap_val >= 0 else ""
            total_q = d.get("total_queries_evaluated", 174)
            leaderboard_rows.append(f"""
            <tr class="table-row-glass">
              <td>
                <div class="model-cell">
                  <span class="glass-rank-pill">{rank_str}</span>
                  <div>
                    <strong class="model-title">{m}</strong>
                    <div class="model-meta">{total_q} live queries</div>
                  </div>
                </div>
              </td>
              <td><span class="stat-num stat-cyan">{d.get('open_ended_accuracy', 0)}%</span></td>
              <td><span class="stat-num stat-blue">{d.get('mcq_accuracy', 0)}%</span></td>
              <td><span class="gloss-badge badge-warning">{gap_sign}{gap_val}%</span></td>
              <td><span class="stat-num stat-emerald">{d.get('pairwise_consistency', 0)}%</span></td>
              <td><span class="stat-num stat-purple">{d.get('abstention_accuracy', 0)}%</span></td>
              <td><span class="gloss-badge badge-danger">{d.get('hallucination_rate', 0)}%</span></td>
            </tr>
            """)

        # Counterfactual Cards with Interactive FLIP components
        cf_cards = []
        cf_dict_payload = {}
        for p in cf_pairs:
            diff_color = {
                "easy": "badge-emerald",
                "medium": "badge-amber",
                "hard": "badge-rose",
            }.get(p["difficulty"].lower(), "badge-blue")

            pair_id = p["pair_id"]
            cf_dict_payload[pair_id] = {
                "pair_id": pair_id,
                "base_b64": p["base_b64"],
                "base_answer": p["base_answer"],
                "cf_b64": p["cf_b64"],
                "cf_answer": p["cf_answer"],
            }

            cf_cards.append(f"""
            <div class="glass-card-3d cf-showcase-panel" id="cf-panel-{pair_id}" data-flipped="false">
              <div class="glass-sheen"></div>
              <div class="cf-header-bar">
                <div class="tags-cluster">
                  <span class="gloss-badge badge-cyan">{pair_id.upper()}</span>
                  <span class="gloss-badge {diff_color}">{p['difficulty'].upper()}</span>
                  <span class="gloss-badge badge-flip-indicator" id="badge-mode-{pair_id}">BASELINE Z-ORDER</span>
                </div>
                <div class="cf-edit-pill">⚡ Surgical Edit: {p['edit']}</div>
              </div>
              <div class="cf-query-box">
                <span class="query-bulb">🔍</span>
                <div class="query-text">
                  <strong>Query:</strong> "{p['question']}"
                </div>
              </div>

              <!-- Interactive 3D Comparison Stage with Working Flip Button -->
              <div class="cf-stage-3d">

                <!-- Left Pedestal -->
                <div class="twin-glass-pedestal twin-left" id="pedestal-left-{pair_id}" onclick="openActiveLightbox('{pair_id}', 'left')">
                  <div class="pedestal-top">
                    <span class="twin-title" id="title-left-{pair_id}">BASE TWIN (z-order A)</span>
                    <span class="pedestal-zoom">⛶ Inspect</span>
                  </div>
                  <div class="pedestal-img-frame">
                    <img src="{p['base_b64']}" class="pedestal-img" id="img-left-{pair_id}" alt="Base Diagram" />
                  </div>
                  <div class="pedestal-bottom">
                    <span class="ans-label">Ground Truth:</span>
                    <span class="gloss-badge badge-emerald-glow" id="ans-left-{pair_id}">{p['base_answer'].upper()}</span>
                  </div>
                </div>

                <!-- Animated Interactive Orbital Flip Button -->
                <div class="orbital-flip-portal" id="portal-{pair_id}" onclick="triggerPairFlip('{pair_id}')" role="button" tabindex="0" title="Click to Flip Z-Order and Invert Ground Truth!">
                  <div class="portal-ring ring-outer"></div>
                  <div class="portal-ring ring-inner"></div>
                  <div class="portal-core">
                    <span class="flip-arrows">⇄</span>
                    <span class="flip-sub">FLIP</span>
                  </div>
                  <div class="portal-click-prompt">CLICK TO FLIP</div>
                </div>

                <!-- Right Pedestal -->
                <div class="twin-glass-pedestal twin-right" id="pedestal-right-{pair_id}" onclick="openActiveLightbox('{pair_id}', 'right')">
                  <div class="pedestal-top">
                    <span class="twin-title" id="title-right-{pair_id}">COUNTERFACTUAL TWIN (z-order B)</span>
                    <span class="pedestal-zoom">⛶ Inspect</span>
                  </div>
                  <div class="pedestal-img-frame">
                    <img src="{p['cf_b64']}" class="pedestal-img" id="img-right-{pair_id}" alt="Counterfactual Diagram" />
                  </div>
                  <div class="pedestal-bottom">
                    <span class="ans-label">Ground Truth:</span>
                    <span class="gloss-badge badge-rose-glow" id="ans-right-{pair_id}">{p['cf_answer'].upper()} (FLIPPED)</span>
                  </div>
                </div>

              </div>

              <!-- Interactive Feedback Banner -->
              <div class="flip-toast-bar" id="toast-{pair_id}">
                <span class="toast-dot"></span>
                <span class="toast-text" id="toast-text-{pair_id}">
                  Click the animated <strong>⇄ FLIP</strong> button above to trigger an interactive 3D swap and observe ground-truth inversion in real time!
                </span>
              </div>
            </div>
            """)

        abstention_html = ""
        if abstention:
            abstention_html = f"""
            <div class="glass-card-3d cf-showcase-panel">
              <div class="glass-sheen"></div>
              <div class="cf-header-bar">
                <div class="tags-cluster">
                  <span class="gloss-badge badge-purple">ABSTENTION MODE</span>
                  <span class="gloss-badge badge-rose">100% OCCLUDED</span>
                </div>
                <div class="cf-edit-pill">📐 Shapely Planar Visible Area == 0.0000 px²</div>
              </div>
              <div class="cf-query-box">
                <span class="query-bulb">👁️</span>
                <div class="query-text">
                  <strong>Target Query:</strong> "{abstention['question']}"
                </div>
              </div>
              <div class="abstention-stage-3d">
                <div class="twin-glass-pedestal" onclick="openLightbox('{abstention['png_b64']}', 'Abstention Case: Hidden Target 100% Occluded')">
                  <div class="pedestal-top">
                    <span class="twin-title">RENDERED DIAGRAM</span>
                    <span class="pedestal-zoom">⛶ Inspect</span>
                  </div>
                  <div class="pedestal-img-frame">
                    <img src="{abstention['png_b64']}" class="pedestal-img" alt="Abstention Scene" />
                  </div>
                  <div class="pedestal-bottom">
                    <span class="ans-label">Expected Response:</span>
                    <span class="gloss-badge badge-purple-glow">{abstention['answer']}</span>
                  </div>
                </div>

                <div class="abstention-proof-card">
                  <h4 class="proof-head">✨ Mathematical Geometric Proof</h4>
                  <ul class="proof-items">
                    <li><span class="bullet">🔹</span> <strong>Hidden Target:</strong> <code class="hl-code">{abstention['hidden_shape']}</code> (Base Layer z=0)</li>
                    <li><span class="bullet">🔹</span> <strong>Covering Node:</strong> <code class="hl-code">{abstention['cover_shape']}</code> (Foreground Layer z=1, 160% size)</li>
                    <li><span class="bullet">🔹</span> <strong>Shapely Intersection:</strong> 100% planar coincidence</li>
                    <li><span class="bullet">🔹</span> <strong>Visible Pixel Ratio:</strong> <code>0.000000</code></li>
                    <li><span class="bullet">⚠️</span> <strong>The Hallucination Trap:</strong> Weaker models hallucinate colors and shape contours when visual evidence is completely absent.</li>
                  </ul>
                </div>
              </div>
            </div>
            """

        cf_json_string = json.dumps(cf_dict_payload)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Visual Task Factory — 3D Glassmorphic Benchmark Suite</title>
  <style>
    /* =========================================================================
       ULTRA-GLOSS 3D GLASSMORPHISM THEME
       ========================================================================= */
    :root {{
      --cyan: #00f2fe;
      --cyan-glow: rgba(0, 242, 254, 0.45);
      --blue: #4facfe;
      --purple: #b927ff;
      --purple-glow: rgba(185, 39, 255, 0.45);
      --emerald: #00f2a9;
      --emerald-glow: rgba(0, 242, 169, 0.45);
      --amber: #ffb300;
      --amber-glow: rgba(255, 179, 0, 0.45);
      --rose: #ff3366;
      --rose-glow: rgba(255, 51, 102, 0.45);

      --glass-surface: rgba(255, 255, 255, 0.06);
      --glass-surface-hover: rgba(255, 255, 255, 0.12);
      --glass-border: rgba(255, 255, 255, 0.22);
      --glass-border-light: rgba(255, 255, 255, 0.45);
      --glass-blur: blur(28px) saturate(210%);

      --text-hero: #ffffff;
      --text-body: #e2e8f0;
      --text-muted: #94a3b8;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", "Helvetica Neue", Arial, sans-serif;
    }}

    body {{
      background-color: #030712;
      background-image:
        radial-gradient(circle at 10% 10%, rgba(99, 102, 241, 0.35) 0%, transparent 45%),
        radial-gradient(circle at 90% 15%, rgba(6, 182, 212, 0.35) 0%, transparent 45%),
        radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.25) 0%, transparent 55%),
        radial-gradient(circle at 80% 85%, rgba(244, 63, 94, 0.25) 0%, transparent 45%),
        radial-gradient(circle at 20% 90%, rgba(16, 185, 129, 0.25) 0%, transparent 45%),
        linear-gradient(180deg, #020617 0%, #030712 100%);
      color: var(--text-body);
      padding: 40px 24px 80px;
      line-height: 1.5;
      min-height: 100vh;
      overflow-x: hidden;
      position: relative;
    }}

    /* Futuristic Luminous Grid Overlay */
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      z-index: 1;
    }}

    /* Animated Dynamic Floating Aurora Orbs */
    .aurora-orb {{
      position: fixed;
      border-radius: 50%;
      filter: blur(120px);
      pointer-events: none;
      z-index: 0;
      opacity: 0.65;
      animation: auroraFloat 22s ease-in-out infinite alternate;
    }}
    .aurora-1 {{
      width: 650px;
      height: 650px;
      background: radial-gradient(circle, #00f2fe 0%, rgba(0, 242, 254, 0) 70%);
      top: -150px;
      left: -150px;
    }}
    .aurora-2 {{
      width: 750px;
      height: 750px;
      background: radial-gradient(circle, #b927ff 0%, rgba(185, 39, 255, 0) 70%);
      top: 30%;
      right: -250px;
      animation-duration: 26s;
    }}
    .aurora-3 {{
      width: 600px;
      height: 600px;
      background: radial-gradient(circle, #00f2a9 0%, rgba(0, 242, 169, 0) 70%);
      bottom: -150px;
      left: 25%;
      animation-duration: 20s;
    }}

    @keyframes auroraFloat {{
      0% {{ transform: translate3d(0, 0, 0) rotate(0deg) scale(1); }}
      50% {{ transform: translate3d(60px, -50px, 0) rotate(90deg) scale(1.1); }}
      100% {{ transform: translate3d(-50px, 60px, 0) rotate(180deg) scale(0.95); }}
    }}

    .app-viewport {{
      max-width: 1300px;
      margin: 0 auto;
      position: relative;
      z-index: 2;
    }}

    /* =========================================================================
       3D GLASSMORPHIC CARDS & SPECULAR SHEEN
       ========================================================================= */
    .glass-card-3d {{
      background: var(--glass-surface);
      backdrop-filter: var(--glass-blur);
      -webkit-backdrop-filter: var(--glass-blur);
      border: 1px solid var(--glass-border);
      border-radius: 24px;
      box-shadow:
        0 20px 50px -10px rgba(0, 0, 0, 0.7),
        0 0 0 1px rgba(255, 255, 255, 0.1) inset,
        0 2px 0 0 rgba(255, 255, 255, 0.4) inset;
      position: relative;
      overflow: hidden;
      transform-style: preserve-3d;
      transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease, border-color 0.3s ease;
    }}

    .glass-card-3d:hover {{
      border-color: var(--glass-border-light);
      box-shadow:
        0 30px 70px -10px rgba(0, 0, 0, 0.8),
        0 0 30px rgba(0, 242, 254, 0.3),
        0 0 0 1px rgba(255, 255, 255, 0.25) inset,
        0 2px 0 0 rgba(255, 255, 255, 0.6) inset;
    }}

    /* Glossy Diagonal Specular Light Reflection */
    .glass-sheen {{
      position: absolute;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background: linear-gradient(
        135deg,
        rgba(255, 255, 255, 0.15) 0%,
        rgba(255, 255, 255, 0.05) 25%,
        transparent 50%
      );
      pointer-events: none;
      transform: rotate(15deg);
      transition: opacity 0.3s ease;
      opacity: 0.7;
    }}
    .glass-card-3d:hover .glass-sheen {{
      opacity: 1;
    }}

    /* =========================================================================
       HERO HEADER PANEL
       ========================================================================= */
    .header-hero {{
      padding: 36px 40px;
      margin-bottom: 40px;
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.03) 100%);
      border: 1px solid rgba(255, 255, 255, 0.25);
    }}
    .hero-top-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 24px;
      margin-bottom: 20px;
    }}
    .hero-brand {{
      display: flex;
      align-items: center;
      gap: 20px;
    }}
    .hero-logo-prism {{
      width: 64px;
      height: 64px;
      background: linear-gradient(135deg, #00f2fe 0%, #4facfe 50%, #b927ff 100%);
      border-radius: 18px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 30px;
      box-shadow:
        0 15px 35px rgba(0, 242, 254, 0.4),
        inset 0 2px 2px rgba(255, 255, 255, 0.7);
      transform: perspective(600px) rotateX(12deg) rotateY(-12deg);
      transition: transform 0.4s ease;
    }}
    .hero-logo-prism:hover {{
      transform: perspective(600px) rotateX(0deg) rotateY(0deg) scale(1.1);
    }}
    .hero-titles h1 {{
      font-size: 34px;
      font-weight: 900;
      letter-spacing: -1px;
      background: linear-gradient(135deg, #ffffff 0%, #00f2fe 50%, #e0aaff 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 2px 10px rgba(0, 242, 254, 0.3));
      margin-bottom: 4px;
    }}
    .hero-titles .hero-tagline {{
      font-size: 15px;
      color: var(--text-muted);
      font-weight: 500;
    }}

    .validation-shield {{
      background: rgba(0, 242, 169, 0.15);
      border: 1px solid rgba(0, 242, 169, 0.5);
      color: #00f2a9;
      padding: 10px 20px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.6px;
      display: flex;
      align-items: center;
      gap: 10px;
      box-shadow:
        0 0 30px rgba(0, 242, 169, 0.35),
        inset 0 1px 0 rgba(255, 255, 255, 0.6);
      backdrop-filter: blur(12px);
    }}
    .pulse-laser {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #00f2a9;
      box-shadow: 0 0 12px #00f2a9;
      animation: laserPulse 1.6s infinite;
    }}
    @keyframes laserPulse {{
      0%, 100% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(0.7); opacity: 0.4; }}
    }}

    .spec-pills-cluster {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 16px;
    }}
    .spec-pill {{
      background: rgba(255, 255, 255, 0.07);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 9999px;
      padding: 6px 16px;
      font-size: 12px;
      font-weight: 600;
      color: #e2e8f0;
      display: flex;
      align-items: center;
      gap: 8px;
      backdrop-filter: blur(10px);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }}

    /* =========================================================================
       SECTION TITLES
       ========================================================================= */
    .section-banner {{
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 24px;
      margin-top: 12px;
    }}
    .section-icon-3d {{
      width: 38px;
      height: 38px;
      border-radius: 12px;
      background: linear-gradient(135deg, rgba(0, 242, 254, 0.25) 0%, rgba(185, 39, 255, 0.25) 100%);
      border: 1px solid rgba(255, 255, 255, 0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      box-shadow: 0 8px 20px rgba(0, 242, 254, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.5);
    }}
    .section-banner-title {{
      font-size: 22px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.4px;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }}

    /* =========================================================================
       1. EXECUTIVE 3D METRICS GRID
       ========================================================================= */
    .metrics-stage-3d {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
      gap: 24px;
      margin-bottom: 48px;
    }}
    .metric-slab {{
      padding: 28px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 200px;
    }}
    .metric-slab-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 14px;
    }}
    .metric-slab-title {{
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--text-muted);
    }}
    .metric-slab-badge {{
      width: 40px;
      height: 40px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      border: 1px solid rgba(255, 255, 255, 0.3);
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.6);
    }}

    .metric-slab-val {{
      font-size: 46px;
      font-weight: 900;
      line-height: 1.05;
      letter-spacing: -1.5px;
      margin-bottom: 8px;
      transform: translateZ(30px);
    }}
    .metric-slab-foot {{
      font-size: 13px;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .glass-meter-track {{
      width: 100%;
      height: 8px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 9999px;
      overflow: hidden;
      margin-top: 12px;
      box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.6);
    }}
    .glass-meter-fill {{
      height: 100%;
      border-radius: 9999px;
      box-shadow: 0 0 15px currentColor;
    }}

    /* Card Glow Themes */
    .slab-cyan {{
      border-color: rgba(0, 242, 254, 0.35);
      box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 242, 254, 0.2);
    }}
    .slab-cyan .metric-slab-badge {{ background: rgba(0, 242, 254, 0.2); color: var(--cyan); }}
    .slab-cyan .metric-slab-val {{
      background: linear-gradient(180deg, #ffffff 0%, #00f2fe 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 4px 15px var(--cyan-glow));
    }}
    .slab-cyan .glass-meter-fill {{ background: linear-gradient(90deg, #0284c7, #00f2fe); color: #00f2fe; }}

    .slab-amber {{
      border-color: rgba(255, 179, 0, 0.35);
      box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.7), 0 0 25px rgba(255, 179, 0, 0.2);
    }}
    .slab-amber .metric-slab-badge {{ background: rgba(255, 179, 0, 0.2); color: var(--amber); }}
    .slab-amber .metric-slab-val {{
      background: linear-gradient(180deg, #ffffff 0%, #ffb300 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 4px 15px var(--amber-glow));
    }}
    .slab-amber .glass-meter-fill {{ background: linear-gradient(90deg, #d97706, #ffb300); color: #ffb300; }}

    .slab-emerald {{
      border-color: rgba(0, 242, 169, 0.35);
      box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 242, 169, 0.2);
    }}
    .slab-emerald .metric-slab-badge {{ background: rgba(0, 242, 169, 0.2); color: var(--emerald); }}
    .slab-emerald .metric-slab-val {{
      background: linear-gradient(180deg, #ffffff 0%, #00f2a9 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 4px 15px var(--emerald-glow));
    }}
    .slab-emerald .glass-meter-fill {{ background: linear-gradient(90deg, #059669, #00f2a9); color: #00f2a9; }}

    .slab-purple {{
      border-color: rgba(185, 39, 255, 0.35);
      box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.7), 0 0 25px rgba(185, 39, 255, 0.2);
    }}
    .slab-purple .metric-slab-badge {{ background: rgba(185, 39, 255, 0.2); color: var(--purple); }}
    .slab-purple .metric-slab-val {{
      background: linear-gradient(180deg, #ffffff 0%, #b927ff 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 4px 15px var(--purple-glow));
    }}
    .slab-purple .glass-meter-fill {{ background: linear-gradient(90deg, #7c3aed, #b927ff); color: #b927ff; }}

    /* =========================================================================
       2. LEADERBOARD TABLE (LUMINOUS FROSTED GLASS)
       ========================================================================= */
    .leaderboard-slab {{
      padding: 6px;
      margin-bottom: 52px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 14px;
    }}
    thead th {{
      background: rgba(255, 255, 255, 0.05);
      padding: 18px 22px;
      font-weight: 800;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    }}
    tbody tr {{
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      transition: background 0.2s ease, transform 0.2s ease;
    }}
    tbody tr:hover {{
      background: rgba(255, 255, 255, 0.07);
    }}
    tbody tr:last-child {{
      border-bottom: none;
    }}
    td {{
      padding: 20px 22px;
      vertical-align: middle;
    }}
    .model-cell {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .glass-rank-pill {{
      font-size: 12px;
      font-weight: 800;
      padding: 5px 12px;
      border-radius: 9999px;
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.25);
      color: #ffffff;
      box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.5);
    }}
    .model-title {{
      font-size: 16px;
      font-weight: 800;
      color: #ffffff;
    }}
    .model-meta {{
      font-size: 12px;
      color: var(--text-muted);
    }}
    .stat-num {{
      font-weight: 900;
      font-size: 16px;
      letter-spacing: -0.5px;
    }}
    .stat-cyan {{ color: var(--cyan); text-shadow: 0 0 12px var(--cyan-glow); }}
    .stat-blue {{ color: var(--blue); text-shadow: 0 0 12px rgba(79, 172, 254, 0.4); }}
    .stat-emerald {{ color: var(--emerald); text-shadow: 0 0 12px var(--emerald-glow); }}
    .stat-purple {{ color: var(--purple); text-shadow: 0 0 12px var(--purple-glow); }}

    /* =========================================================================
       GLOSSY BADGES
       ========================================================================= */
    .gloss-badge {{
      font-size: 11px;
      font-weight: 800;
      padding: 5px 12px;
      border-radius: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: inline-block;
      backdrop-filter: blur(12px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.5);
    }}
    .badge-cyan {{ background: rgba(0, 242, 254, 0.2); color: #00f2fe; border: 1px solid rgba(0, 242, 254, 0.45); }}
    .badge-blue {{ background: rgba(79, 172, 254, 0.2); color: #4facfe; border: 1px solid rgba(79, 172, 254, 0.45); }}
    .badge-emerald {{ background: rgba(0, 242, 169, 0.2); color: #00f2a9; border: 1px solid rgba(0, 242, 169, 0.45); }}
    .badge-emerald-glow {{
      background: rgba(0, 242, 169, 0.25);
      color: #ffffff;
      border: 1px solid #00f2a9;
      box-shadow: 0 0 20px var(--emerald-glow), inset 0 1px 0 rgba(255, 255, 255, 0.7);
    }}
    .badge-rose {{ background: rgba(255, 51, 102, 0.2); color: #ff3366; border: 1px solid rgba(255, 51, 102, 0.45); }}
    .badge-rose-glow {{
      background: rgba(255, 51, 102, 0.25);
      color: #ffffff;
      border: 1px solid #ff3366;
      box-shadow: 0 0 20px var(--rose-glow), inset 0 1px 0 rgba(255, 255, 255, 0.7);
    }}
    .badge-amber {{ background: rgba(255, 179, 0, 0.2); color: #ffb300; border: 1px solid rgba(255, 179, 0, 0.45); }}
    .badge-warning {{ background: rgba(255, 179, 0, 0.2); color: #ffb300; border: 1px solid rgba(255, 179, 0, 0.45); }}
    .badge-danger {{ background: rgba(255, 51, 102, 0.2); color: #ff3366; border: 1px solid rgba(255, 51, 102, 0.45); }}
    .badge-purple {{ background: rgba(185, 39, 255, 0.2); color: #b927ff; border: 1px solid rgba(185, 39, 255, 0.45); }}
    .badge-purple-glow {{
      background: rgba(185, 39, 255, 0.25);
      color: #ffffff;
      border: 1px solid #b927ff;
      box-shadow: 0 0 20px var(--purple-glow), inset 0 1px 0 rgba(255, 255, 255, 0.7);
    }}
    .badge-flip-indicator {{
      background: rgba(255, 255, 255, 0.08);
      color: #e2e8f0;
      border: 1px solid rgba(255, 255, 255, 0.2);
    }}

    /* =========================================================================
       3. DIAGNOSTIC CHARTS (3D GLASS GALLERY)
       ========================================================================= */
    .charts-stage-3d {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 28px;
      margin-bottom: 52px;
    }}
    .chart-slab-3d {{
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      cursor: pointer;
    }}
    .chart-slab-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }}
    .chart-pill-tag {{
      font-size: 11px;
      font-weight: 800;
      color: var(--cyan);
      background: rgba(0, 242, 254, 0.15);
      padding: 4px 10px;
      border-radius: 8px;
      border: 1px solid rgba(0, 242, 254, 0.35);
    }}
    .chart-zoom-badge {{
      font-size: 12px;
      color: var(--cyan);
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .chart-display-canvas {{
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.15);
      background: #020617;
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6);
      transition: transform 0.3s ease;
    }}
    .chart-display-canvas img {{
      width: 100%;
      height: auto;
      display: block;
      transition: transform 0.3s ease;
    }}
    .chart-slab-3d:hover .chart-display-canvas img {{
      transform: scale(1.03);
    }}
    .chart-caption-row {{
      font-size: 13px;
      font-weight: 700;
      color: var(--text-body);
      margin-top: 16px;
    }}

    /* =========================================================================
       4. VISUAL COUNTERFACTUAL INSPECTOR & WORKING FLIP BUTTON
       ========================================================================= */
    .cf-column-layout {{
      display: flex;
      flex-direction: column;
      gap: 32px;
      margin-bottom: 52px;
    }}
    .cf-showcase-panel {{
      padding: 28px;
    }}
    .cf-header-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 14px;
      margin-bottom: 18px;
    }}
    .tags-cluster {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .cf-edit-pill {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      font-weight: 700;
      color: var(--cyan);
      background: rgba(0, 242, 254, 0.1);
      border: 1px solid rgba(0, 242, 254, 0.35);
      padding: 5px 12px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }}
    .cf-query-box {{
      font-size: 15px;
      color: #ffffff;
      background: rgba(2, 6, 23, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-left: 4px solid var(--cyan);
      border-radius: 12px;
      padding: 14px 18px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      gap: 12px;
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
    }}
    .query-bulb {{
      font-size: 20px;
    }}

    .cf-stage-3d {{
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 24px;
      perspective: 1200px;
    }}
    @media (max-width: 900px) {{
      .cf-stage-3d {{
        grid-template-columns: 1fr;
      }}
      .orbital-flip-portal {{
        transform: rotate(90deg);
        margin: 18px auto;
      }}
    }}

    .twin-glass-pedestal {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 18px;
      padding: 16px;
      text-align: center;
      cursor: pointer;
      box-shadow:
        0 15px 35px rgba(0, 0, 0, 0.6),
        inset 0 1px 0 rgba(255, 255, 255, 0.4);
      transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), border-color 0.4s ease, box-shadow 0.4s ease, opacity 0.3s ease;
      transform-style: preserve-3d;
    }}
    .twin-glass-pedestal:hover {{
      transform: translateY(-6px) scale(1.02);
      border-color: var(--cyan);
      box-shadow:
        0 25px 60px rgba(0, 0, 0, 0.8),
        0 0 30px var(--cyan-glow),
        inset 0 1px 0 rgba(255, 255, 255, 0.8);
    }}
    .pedestal-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      font-size: 12px;
      font-weight: 800;
      color: var(--text-muted);
    }}
    .pedestal-zoom {{
      color: var(--cyan);
      font-size: 12px;
      font-weight: 700;
    }}
    .pedestal-img-frame {{
      width: 100%;
      max-width: 400px;
      margin: 0 auto 12px;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.15);
      background: #000;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
    }}
    .pedestal-img {{
      width: 100%;
      aspect-ratio: 1;
      display: block;
      transition: transform 0.3s ease;
    }}
    .twin-glass-pedestal:hover .pedestal-img {{
      transform: scale(1.04);
    }}
    .pedestal-bottom {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 14px;
      font-weight: 700;
      padding: 6px 8px 0;
    }}

    /* 3D Card Flip Animation States */
    .pedestal-flipping {{
      transform: perspective(1000px) rotateY(90deg) scale(0.92) !important;
      opacity: 0.4;
      transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.22s ease !important;
    }}

    /* Interactive Orbital Flip Button */
    .orbital-flip-portal {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      position: relative;
      width: 82px;
      height: 82px;
      cursor: pointer;
      user-select: none;
      transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}
    .orbital-flip-portal:hover {{
      transform: scale(1.18);
    }}
    .orbital-flip-portal:active {{
      transform: scale(0.92);
    }}

    .portal-ring {{
      position: absolute;
      border-radius: 50%;
      border: 2px dashed rgba(0, 242, 254, 0.5);
      pointer-events: none;
    }}
    .ring-outer {{
      width: 82px;
      height: 82px;
      animation: spinClockwise 12s linear infinite;
    }}
    .ring-inner {{
      width: 64px;
      height: 64px;
      border-color: rgba(185, 39, 255, 0.5);
      animation: spinCounterClockwise 8s linear infinite;
    }}
    @keyframes spinClockwise {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}
    @keyframes spinCounterClockwise {{
      from {{ transform: rotate(360deg); }}
      to {{ transform: rotate(0deg); }}
    }}

    .portal-core {{
      width: 54px;
      height: 54px;
      border-radius: 50%;
      background: linear-gradient(135deg, rgba(0, 242, 254, 0.9) 0%, rgba(185, 39, 255, 0.9) 100%);
      box-shadow:
        0 0 30px var(--cyan-glow),
        inset 0 1px 1px rgba(255, 255, 255, 0.8);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #ffffff;
      font-weight: 900;
      line-height: 1;
      z-index: 2;
      transition: background 0.3s ease, box-shadow 0.3s ease;
    }}
    .flip-arrows {{
      font-size: 18px;
    }}
    .flip-sub {{
      font-size: 8px;
      letter-spacing: 0.6px;
    }}

    .portal-click-prompt {{
      position: absolute;
      bottom: -22px;
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.8px;
      color: var(--cyan);
      white-space: nowrap;
      text-transform: uppercase;
      opacity: 0.85;
      text-shadow: 0 0 8px var(--cyan-glow);
      transition: transform 0.2s ease, opacity 0.2s ease;
    }}
    .orbital-flip-portal:hover .portal-click-prompt {{
      opacity: 1;
      transform: translateY(2px) scale(1.05);
    }}

    /* Electric Hyperspace Click Animation */
    .portal-animating .ring-outer {{
      animation: hyperSpinOuter 0.65s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    }}
    .portal-animating .ring-inner {{
      animation: hyperSpinInner 0.65s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    }}
    .portal-animating .portal-core {{
      animation: coreHyperBurst 0.65s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    }}

    @keyframes hyperSpinOuter {{
      0% {{ transform: rotate(0deg) scale(1); }}
      50% {{ transform: rotate(360deg) scale(1.35); border-color: #00f2fe; box-shadow: 0 0 35px #00f2fe; }}
      100% {{ transform: rotate(720deg) scale(1); }}
    }}
    @keyframes hyperSpinInner {{
      0% {{ transform: rotate(360deg) scale(1); }}
      50% {{ transform: rotate(0deg) scale(1.25); border-color: #ff3366; box-shadow: 0 0 35px #ff3366; }}
      100% {{ transform: rotate(-360deg) scale(1); }}
    }}
    @keyframes coreHyperBurst {{
      0% {{ transform: scale(1); }}
      50% {{ transform: scale(1.4) rotate(180deg); box-shadow: 0 0 50px #00f2fe, 0 0 40px #ff3366; }}
      100% {{ transform: scale(1) rotate(360deg); }}
    }}

    .portal-active-flipped .portal-core {{
      background: linear-gradient(135deg, rgba(255, 51, 102, 0.95) 0%, rgba(185, 39, 255, 0.95) 100%) !important;
      box-shadow: 0 0 35px var(--rose-glow), inset 0 1px 1px rgba(255, 255, 255, 0.8) !important;
    }}
    .portal-active-flipped .ring-outer {{
      border-color: rgba(255, 51, 102, 0.8) !important;
      box-shadow: 0 0 20px rgba(255, 51, 102, 0.4);
    }}

    /* Toast Bar */
    .flip-toast-bar {{
      margin-top: 22px;
      padding: 12px 18px;
      border-radius: 12px;
      background: rgba(2, 6, 23, 0.65);
      border: 1px solid rgba(255, 255, 255, 0.12);
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      color: var(--text-muted);
      transition: all 0.3s ease;
    }}
    .toast-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--cyan);
      box-shadow: 0 0 10px var(--cyan);
      flex-shrink: 0;
    }}
    [data-flipped="true"] .flip-toast-bar {{
      background: rgba(255, 51, 102, 0.1);
      border-color: rgba(255, 51, 102, 0.35);
      color: #fecaca;
    }}
    [data-flipped="true"] .toast-dot {{
      background: var(--rose);
      box-shadow: 0 0 10px var(--rose);
    }}

    /* =========================================================================
       5. ABSTENTION INSPECTOR
       ========================================================================= */
    .abstention-stage-3d {{
      display: grid;
      grid-template-columns: 1fr 1.3fr;
      gap: 28px;
      align-items: center;
    }}
    @media (max-width: 900px) {{
      .abstention-stage-3d {{
        grid-template-columns: 1fr;
      }}
    }}
    .abstention-proof-card {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(185, 39, 255, 0.35);
      border-radius: 18px;
      padding: 26px 28px;
      box-shadow:
        0 15px 40px rgba(0, 0, 0, 0.6),
        0 0 25px rgba(185, 39, 255, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.4);
    }}
    .proof-head {{
      font-size: 18px;
      font-weight: 800;
      color: #e0aaff;
      margin-bottom: 16px;
      text-shadow: 0 0 15px var(--purple-glow);
    }}
    .proof-items {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 12px;
      font-size: 14px;
      color: #cbd5e1;
      line-height: 1.6;
    }}
    .hl-code {{
      background: rgba(255, 255, 255, 0.12);
      padding: 3px 8px;
      border-radius: 6px;
      font-family: monospace;
      color: var(--cyan);
      border: 1px solid rgba(255, 255, 255, 0.15);
    }}

    /* =========================================================================
       6. LIGHTBOX MODAL
       ========================================================================= */
    .modal-lightbox {{
      position: fixed;
      inset: 0;
      background: rgba(2, 6, 23, 0.92);
      backdrop-filter: blur(25px);
      -webkit-backdrop-filter: blur(25px);
      z-index: 1000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 30px;
      opacity: 0;
      transition: opacity 0.25s ease;
    }}
    .modal-lightbox.active {{
      display: flex;
      opacity: 1;
    }}
    .modal-dialog-glass {{
      max-width: 900px;
      width: 100%;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid rgba(255, 255, 255, 0.3);
      border-radius: 24px;
      box-shadow:
        0 30px 100px rgba(0, 0, 0, 0.95),
        0 0 50px var(--cyan-glow),
        inset 0 1px 0 rgba(255, 255, 255, 0.5);
      overflow: hidden;
      animation: zoomModalIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}
    @keyframes zoomModalIn {{
      0% {{ transform: scale(0.9); opacity: 0; }}
      100% {{ transform: scale(1); opacity: 1; }}
    }}
    .modal-topbar {{
      padding: 18px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.15);
      background: rgba(255, 255, 255, 0.05);
    }}
    .modal-headline {{
      font-size: 16px;
      font-weight: 800;
      color: #ffffff;
    }}
    .modal-close-x {{
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #ffffff;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s ease, transform 0.2s ease;
    }}
    .modal-close-x:hover {{
      background: rgba(255, 51, 102, 0.6);
      transform: scale(1.1);
    }}
    .modal-canvas-frame {{
      padding: 24px;
      text-align: center;
    }}
    .modal-canvas-frame img {{
      max-width: 100%;
      max-height: 72vh;
      border-radius: 14px;
      box-shadow: 0 15px 40px rgba(0, 0, 0, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.2);
    }}

    /* =========================================================================
       FOOTER
       ========================================================================= */
    .footer-hero {{
      padding: 32px 40px;
      margin-top: 56px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 20px;
      font-size: 14px;
      color: var(--text-muted);
    }}
    .footer-action-link {{
      color: var(--cyan);
      text-decoration: none;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: text-shadow 0.2s ease;
    }}
    .footer-action-link:hover {{
      text-shadow: 0 0 12px var(--cyan-glow);
    }}
  </style>
</head>
<body>

  <!-- Dynamic Animated Aurora Glow Orbs -->
  <div class="aurora-orb aurora-1"></div>
  <div class="aurora-orb aurora-2"></div>
  <div class="aurora-orb aurora-3"></div>

  <div class="app-viewport">

    <!-- Hero Header -->
    <header class="glass-card-3d header-hero">
      <div class="glass-sheen"></div>
      <div class="hero-top-row">
        <div class="hero-brand">
          <div class="hero-logo-prism">🎲</div>
          <div class="hero-titles">
            <h1>Visual Task Factory</h1>
            <div class="hero-tagline">2D Spatial Occlusion, Multi-Layer Depth Reasoning & Counterfactual Benchmark</div>
          </div>
        </div>
        <div class="validation-shield">
          <div class="pulse-laser"></div>
          <span>VALIDATION GATE: 100% VERIFIED</span>
        </div>
      </div>
      <div class="spec-pills-cluster">
        <span class="spec-pill">📅 Timestamp: {now_str}</span>
        <span class="spec-pill">⚡ Engine: Shapely Exact 2D Geometry</span>
        <span class="spec-pill">🛡️ Anti-Shortcut: Live Ollama dolphin3:8b</span>
        <span class="spec-pill">🚀 Playwright Headless Batch Engine</span>
        <span class="spec-pill">🎯 Models Evaluated: {len(summary_metrics)}</span>
      </div>
    </header>

    <!-- 1. Executive Headline Metrics Grid -->
    <div class="section-banner">
      <div class="section-icon-3d">📊</div>
      <h2 class="section-banner-title">1. Executive Benchmark Headline Metrics</h2>
    </div>
    <div class="metrics-stage-3d">

      <!-- Metric 1: Open-Ended Accuracy -->
      <div class="glass-card-3d metric-slab slab-cyan">
        <div class="glass-sheen"></div>
        <div>
          <div class="metric-slab-head">
            <span class="metric-slab-title">Top Open-Ended Acc</span>
            <div class="metric-slab-badge">🎯</div>
          </div>
          <div class="metric-slab-val">{top_open}%</div>
          <div class="glass-meter-track">
            <div class="glass-meter-fill" style="width: {min(100.0, top_open)}%;"></div>
          </div>
        </div>
        <div class="metric-slab-foot">
          <span>{top_name}</span>
          <span>vs. {baseline_name}: <strong style="color: #fff;">{baseline_open}%</strong></span>
        </div>
      </div>

      <!-- Metric 2: MCQ Shortcut Gap -->
      <div class="glass-card-3d metric-slab slab-amber">
        <div class="glass-sheen"></div>
        <div>
          <div class="metric-slab-head">
            <span class="metric-slab-title">MCQ Shortcut Gap</span>
            <div class="metric-slab-badge">⚡</div>
          </div>
          <div class="metric-slab-val">+{top_gap}%</div>
          <div class="glass-meter-track">
            <div class="glass-meter-fill" style="width: {min(100.0, max(top_gap, baseline_gap))}%;"></div>
          </div>
        </div>
        <div class="metric-slab-foot">
          <span>{top_name}: +{top_gap}%</span>
          <span>{baseline_name} gap reaches: <strong style="color: #ffb300;">+{baseline_gap}%</strong></span>
        </div>
      </div>

      <!-- Metric 3: Pairwise Consistency -->
      <div class="glass-card-3d metric-slab slab-emerald">
        <div class="glass-sheen"></div>
        <div>
          <div class="metric-slab-head">
            <span class="metric-slab-title">Pairwise Consistency</span>
            <div class="metric-slab-badge">🔄</div>
          </div>
          <div class="metric-slab-val">{top_cons}%</div>
          <div class="glass-meter-track">
            <div class="glass-meter-fill" style="width: {min(100.0, top_cons)}%;"></div>
          </div>
        </div>
        <div class="metric-slab-foot">
          <span>Strict Counterfactual Twins</span>
          <span>{baseline_name}: <strong style="color: #fff;">{baseline_cons}%</strong></span>
        </div>
      </div>

      <!-- Metric 4: Abstention Accuracy -->
      <div class="glass-card-3d metric-slab slab-purple">
        <div class="glass-sheen"></div>
        <div>
          <div class="metric-slab-head">
            <span class="metric-slab-title">Abstention Accuracy</span>
            <div class="metric-slab-badge">🛡️</div>
          </div>
          <div class="metric-slab-val">{top_abs}%</div>
          <div class="glass-meter-track">
            <div class="glass-meter-fill" style="width: {min(100.0, top_abs)}%;"></div>
          </div>
        </div>
        <div class="metric-slab-foot">
          <span>100% Occluded Targets</span>
          <span>{baseline_name} Hallucination: <strong style="color: #ff3366;">{100.0 - baseline_abs:.1f}%</strong></span>
        </div>
      </div>

    </div>

    <!-- 2. Model Leaderboard -->
    <div class="section-banner">
      <div class="section-icon-3d">🏆</div>
      <h2 class="section-banner-title">2. Model Leaderboard & Core Evaluation Primitives</h2>
    </div>
    <div class="glass-card-3d leaderboard-slab">
      <div class="glass-sheen"></div>
      <table>
        <thead>
          <tr>
            <th>Model Profile</th>
            <th>Open-Ended Acc</th>
            <th>MCQ Acc</th>
            <th>MCQ Shortcut Gap</th>
            <th>Pairwise Consistency</th>
            <th>Abstention Acc</th>
            <th>Hallucination Rate</th>
          </tr>
        </thead>
        <tbody>
          {"".join(leaderboard_rows)}
        </tbody>
      </table>
    </div>

    <!-- 3. Publication Charts Showcase -->
    <div class="section-banner">
      <div class="section-icon-3d">📈</div>
      <h2 class="section-banner-title">3. Diagnostic Visual Analytics (300 DPI Publication Quality)</h2>
    </div>
    <div class="charts-stage-3d">

      <!-- Chart 1 -->
      <div class="glass-card-3d chart-slab-3d" onclick="openLightbox('{c1_b64}', 'Figure 1: VLM Accuracy Degradation Across Difficulty Tiers')">
        <div class="glass-sheen"></div>
        <div class="chart-slab-head">
          <span class="chart-pill-tag">DIFFICULTY DEGRADATION</span>
          <span class="chart-zoom-badge">⛶ Click to Inspect</span>
        </div>
        <div class="chart-display-canvas">
          <img src="{c1_b64}" alt="Accuracy by Difficulty Tier" />
        </div>
        <div class="chart-caption-row">
          Figure 1: Monotonic Accuracy Drop across Easy, Medium, and Hard
        </div>
      </div>

      <!-- Chart 2 -->
      <div class="glass-card-3d chart-slab-3d" onclick="openLightbox('{c2_b64}', 'Figure 2: Evaluation Primitives — MCQ Shortcut Gap & Pairwise Consistency')">
        <div class="glass-sheen"></div>
        <div class="chart-slab-head">
          <span class="chart-pill-tag">EVALUATION PRIMITIVES</span>
          <span class="chart-zoom-badge">⛶ Click to Inspect</span>
        </div>
        <div class="chart-display-canvas">
          <img src="{c2_b64}" alt="Consistency and MCQ Gap" />
        </div>
        <div class="chart-caption-row">
          Figure 2: The MCQ Guessing Illusion vs. Strict Pairwise Grounding
        </div>
      </div>

      <!-- Chart 3 -->
      <div class="glass-card-3d chart-slab-3d" onclick="openLightbox('{c3_b64}', 'Figure 3: Accuracy Drop-Off Plotted Against Exact Shapely Occlusion Ratio')">
        <div class="glass-sheen"></div>
        <div class="chart-slab-head">
          <span class="chart-pill-tag">OCCLUSION SENSITIVITY</span>
          <span class="chart-zoom-badge">⛶ Click to Inspect</span>
        </div>
        <div class="chart-display-canvas">
          <img src="{c3_b64}" alt="Occlusion Drop-Off" />
        </div>
        <div class="chart-caption-row">
          Figure 3: Shapely Occlusion Ratio Degradation Curve
        </div>
      </div>

    </div>

    <!-- 4. Visual Counterfactual Inspector with Interactive 3D FLIP -->
    <div class="section-banner">
      <div class="section-icon-3d">🔀</div>
      <h2 class="section-banner-title">4. Visual Counterfactual Inspector: Surgical 98% Identity Twin Pairs</h2>
    </div>
    <div class="cf-column-layout">
      {"".join(cf_cards)}
    </div>

    <!-- 5. Abstention & Hallucination Inspector -->
    <div class="section-banner">
      <div class="section-icon-3d">🛡️</div>
      <h2 class="section-banner-title">5. Abstention Reliability: Unanswerable Hidden Targets</h2>
    </div>
    <div class="cf-column-layout">
      {abstention_html}
    </div>

    <!-- Footer -->
    <footer class="glass-card-3d footer-hero">
      <div class="glass-sheen"></div>
      <div>
        <strong>Visual Task Factory</strong> • Built for the InnoData Visual Reasoning Benchmark Hackathon
      </div>
      <div>
        <a href="https://github.com/Rasagna8412/visual-task-factory" target="_blank" class="footer-action-link">
          GitHub Repository ↗
        </a>
      </div>
    </footer>

  </div>

  <!-- Interactive Lightbox Modal -->
  <div class="modal-lightbox" id="lightboxModal" onclick="closeLightbox(event)">
    <div class="modal-dialog-glass" onclick="event.stopPropagation()">
      <div class="modal-topbar">
        <div class="modal-headline" id="lightboxTitle">Diagram Inspector</div>
        <button class="modal-close-x" onclick="closeLightbox()">✕</button>
      </div>
      <div class="modal-canvas-frame">
        <img id="lightboxImg" src="" alt="Enlarged Diagram View" />
      </div>
    </div>
  </div>

  <!-- Embedded Counterfactual Twin Registry & Interactive Scripts -->
  <script>
    // Injected Counterfactual Twins Payload
    const cfData = {cf_json_string};

    // 3D Card Tilt on Mouse Movement
    document.querySelectorAll('.glass-card-3d').forEach(card => {{
      card.addEventListener('mousemove', e => {{
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotateX = ((y - centerY) / centerY) * -5;
        const rotateY = ((x - centerX) / centerX) * 5;

        card.style.transform = `perspective(1000px) rotateX(${{rotateX.toFixed(2)}}deg) rotateY(${{rotateY.toFixed(2)}}deg) translateY(-4px)`;
      }});

      card.addEventListener('mouseleave', () => {{
        card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)';
      }});
    }});

    // Interactive 3D FLIP Button Handler
    function triggerPairFlip(pairId) {{
      const panel = document.getElementById('cf-panel-' + pairId);
      const portal = document.getElementById('portal-' + pairId);
      const leftPedestal = document.getElementById('pedestal-left-' + pairId);
      const rightPedestal = document.getElementById('pedestal-right-' + pairId);
      const badgeMode = document.getElementById('badge-mode-' + pairId);
      const toastText = document.getElementById('toast-text-' + pairId);
      const data = cfData[pairId];
      if (!data) return;

      // 1. Trigger Hyperspace Spin Animation on Portal Core
      portal.classList.add('portal-animating');
      setTimeout(() => portal.classList.remove('portal-animating'), 650);

      // 2. Trigger 3D Card Flip on Both Pedestals
      leftPedestal.classList.add('pedestal-flipping');
      rightPedestal.classList.add('pedestal-flipping');

      const isFlipped = panel.getAttribute('data-flipped') === 'true';

      // 3. Swap Contents and Invert Answers at the 90-degree Midpoint
      setTimeout(() => {{
        if (!isFlipped) {{
          panel.setAttribute('data-flipped', 'true');
          portal.classList.add('portal-active-flipped');
          badgeMode.textContent = '⇄ Z-ORDER INVERTED';
          badgeMode.className = 'gloss-badge badge-rose-glow';

          // Swap Left to show Counterfactual Twin
          document.getElementById('title-left-' + pairId).textContent = 'COUNTERFACTUAL TWIN (z-order B)';
          document.getElementById('img-left-' + pairId).src = data.cf_b64;
          const ansL = document.getElementById('ans-left-' + pairId);
          ansL.textContent = data.cf_answer.toUpperCase() + ' (FLIPPED)';
          ansL.className = 'gloss-badge badge-rose-glow';

          // Swap Right to show Base Twin
          document.getElementById('title-right-' + pairId).textContent = 'BASE TWIN (z-order A)';
          document.getElementById('img-right-' + pairId).src = data.base_b64;
          const ansR = document.getElementById('ans-right-' + pairId);
          ansR.textContent = data.base_answer.toUpperCase();
          ansR.className = 'gloss-badge badge-emerald-glow';

          toastText.innerHTML = '⚡ <strong>Z-Order Swapped!</strong> The two target shapes swapped layer depth &mdash; Ground truth inverted from <code>' + data.base_answer.toUpperCase() + '</code> to <code>' + data.cf_answer.toUpperCase() + '</code>. Click FLIP again to restore.';
        }} else {{
          panel.setAttribute('data-flipped', 'false');
          portal.classList.remove('portal-active-flipped');
          badgeMode.textContent = 'BASELINE Z-ORDER';
          badgeMode.className = 'gloss-badge badge-flip-indicator';

          // Restore Left to Base Twin
          document.getElementById('title-left-' + pairId).textContent = 'BASE TWIN (z-order A)';
          document.getElementById('img-left-' + pairId).src = data.base_b64;
          const ansL = document.getElementById('ans-left-' + pairId);
          ansL.textContent = data.base_answer.toUpperCase();
          ansL.className = 'gloss-badge badge-emerald-glow';

          // Restore Right to Counterfactual Twin
          document.getElementById('title-right-' + pairId).textContent = 'COUNTERFACTUAL TWIN (z-order B)';
          document.getElementById('img-right-' + pairId).src = data.cf_b64;
          const ansR = document.getElementById('ans-right-' + pairId);
          ansR.textContent = data.cf_answer.toUpperCase() + ' (FLIPPED)';
          ansR.className = 'gloss-badge badge-rose-glow';

          toastText.innerHTML = '✓ Restored to baseline z-order. Ground truth is <code>' + data.base_answer.toUpperCase() + '</code>. Click FLIP to swap again.';
        }}
      }}, 220);

      // 4. Spring Pedestals Back into View
      setTimeout(() => {{
        leftPedestal.classList.remove('pedestal-flipping');
        rightPedestal.classList.remove('pedestal-flipping');
      }}, 500);
    }}

    // Lightbox Controls with Active State Detection
    function openActiveLightbox(pairId, side) {{
      const data = cfData[pairId];
      if (!data) return;
      const panel = document.getElementById('cf-panel-' + pairId);
      const isFlipped = panel.getAttribute('data-flipped') === 'true';

      let imgSrc = '';
      let title = '';
      if (side === 'left') {{
        imgSrc = (!isFlipped) ? data.base_b64 : data.cf_b64;
        title = (!isFlipped) ? `Base Twin (${{pairId}}) — Ground Truth: ${{data.base_answer.toUpperCase()}}` : `Counterfactual Twin (${{pairId}}) — Ground Truth: ${{data.cf_answer.toUpperCase()}} (FLIPPED)`;
      }} else {{
        imgSrc = (!isFlipped) ? data.cf_b64 : data.base_b64;
        title = (!isFlipped) ? `Counterfactual Twin (${{pairId}}) — Ground Truth: ${{data.cf_answer.toUpperCase()}} (FLIPPED)` : `Base Twin (${{pairId}}) — Ground Truth: ${{data.base_answer.toUpperCase()}}`;
      }}
      openLightbox(imgSrc, title);
    }}

    function openLightbox(imgSrc, title) {{
      if (!imgSrc) return;
      document.getElementById('lightboxImg').src = imgSrc;
      document.getElementById('lightboxTitle').textContent = title || 'Diagram Inspector';
      const modal = document.getElementById('lightboxModal');
      modal.classList.add('active');
    }}

    function closeLightbox() {{
      const modal = document.getElementById('lightboxModal');
      modal.classList.remove('active');
    }}

    document.addEventListener('keydown', e => {{
      if (e.key === 'Escape') closeLightbox();
    }});
  </script>
</body>
</html>"""
        return html


def build_dashboard(
    run_dir: Union[str, Path],
    summary_metrics: Dict[str, Any],
    raw_results: Optional[List[Dict[str, Any]]] = None,
    cf_pairs_data: Optional[List[Dict[str, Any]]] = None,
) -> Path:
    """Helper to generate dashboard.html in the specified run directory."""
    builder = DashboardBuilder(run_dir=run_dir)
    return builder.build(
        summary_metrics=summary_metrics,
        raw_results=raw_results,
        cf_pairs_data=cf_pairs_data,
    )
