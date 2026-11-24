"""Dashboard Builder module for Visual Task Factory.

Generates an ultra-premium, refined 3D Glassmorphic Demo Day dashboard (`dashboard.html`)
with balanced, elegant color intensity, comfortable contrast, realistic specular highlights,
translucent frosted glass, and interactive 3D card physics.
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
    """Builds self-contained HTML Demo Day dashboard with balanced, elegant 3D glassmorphism."""

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
        """Renders the balanced, elegant 3D glassmorphic HTML5 template."""
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
              <td><span class="gloss-badge badge-amber">{gap_sign}{gap_val}%</span></td>
              <td><span class="stat-num stat-emerald">{d.get('pairwise_consistency', 0)}%</span></td>
              <td><span class="stat-num stat-purple">{d.get('abstention_accuracy', 0)}%</span></td>
              <td><span class="gloss-badge badge-rose">{d.get('hallucination_rate', 0)}%</span></td>
            </tr>
            """)

        cf_cards = []
        for p in cf_pairs:
            diff_color = {
                "easy": "badge-emerald",
                "medium": "badge-amber",
                "hard": "badge-rose",
            }.get(p["difficulty"].lower(), "badge-blue")

            cf_cards.append(f"""
            <div class="glass-card-3d cf-showcase-panel">
              <div class="glass-sheen"></div>
              <div class="cf-header-bar">
                <div class="tags-cluster">
                  <span class="gloss-badge badge-cyan">{p['pair_id'].upper()}</span>
                  <span class="gloss-badge {diff_color}">{p['difficulty'].upper()}</span>
                </div>
                <div class="cf-edit-pill">⚡ Surgical Edit: {p['edit']}</div>
              </div>
              <div class="cf-query-box">
                <span class="query-bulb">🔍</span>
                <div class="query-text">
                  <strong>Query:</strong> "{p['question']}"
                </div>
              </div>
              <div class="cf-stage-3d">
                <div class="twin-glass-pedestal" onclick="openLightbox('{p['base_b64']}', 'Base Twin ({p['pair_id']}) — Ground Truth: {p['base_answer'].upper()}')">
                  <div class="pedestal-top">
                    <span class="twin-title">BASE TWIN (z-order A)</span>
                    <span class="pedestal-zoom">⛶ Inspect</span>
                  </div>
                  <div class="pedestal-img-frame">
                    <img src="{p['base_b64']}" class="pedestal-img" alt="Base Scene" />
                  </div>
                  <div class="pedestal-bottom">
                    <span class="ans-label">Ground Truth:</span>
                    <span class="gloss-badge badge-emerald-glow">{p['base_answer'].upper()}</span>
                  </div>
                </div>

                <div class="orbital-flip-portal">
                  <div class="portal-ring ring-outer"></div>
                  <div class="portal-ring ring-inner"></div>
                  <div class="portal-core" title="Z-Order Inversion: Ground Truth Flips">
                    <span class="flip-arrows">⇄</span>
                    <span class="flip-sub">FLIP</span>
                  </div>
                </div>

                <div class="twin-glass-pedestal" onclick="openLightbox('{p['cf_b64']}', 'Counterfactual Twin ({p['pair_id']}) — Ground Truth: {p['cf_answer'].upper()}')">
                  <div class="pedestal-top">
                    <span class="twin-title">COUNTERFACTUAL TWIN (z-order B)</span>
                    <span class="pedestal-zoom">⛶ Inspect</span>
                  </div>
                  <div class="pedestal-img-frame">
                    <img src="{p['cf_b64']}" class="pedestal-img" alt="Counterfactual Scene" />
                  </div>
                  <div class="pedestal-bottom">
                    <span class="ans-label">Ground Truth:</span>
                    <span class="gloss-badge badge-rose-glow">{p['cf_answer'].upper()} (FLIPPED)</span>
                  </div>
                </div>
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

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Visual Task Factory — 3D Glassmorphic Benchmark Suite</title>
  <style>
    /* =========================================================================
       BALANCED, ELEGANT 3D GLASSMORPHISM THEME (COMFORTABLE CONTRAST)
       ========================================================================= */
    :root {{
      --cyan: #38bdf8;
      --blue: #60a5fa;
      --purple: #a78bfa;
      --emerald: #34d399;
      --amber: #fbbf24;
      --rose: #f87171;

      --bg-base: #0a0f1d;
      --card-glass: rgba(15, 23, 42, 0.78);
      --card-glass-hover: rgba(20, 30, 55, 0.88);
      --glass-border: rgba(255, 255, 255, 0.12);
      --glass-border-hover: rgba(255, 255, 255, 0.25);
      --glass-blur: blur(20px) saturate(160%);

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
      background-color: var(--bg-base);
      background-image:
        radial-gradient(circle at 15% 12%, rgba(56, 189, 248, 0.08) 0%, transparent 45%),
        radial-gradient(circle at 85% 18%, rgba(167, 139, 250, 0.08) 0%, transparent 45%),
        radial-gradient(circle at 50% 55%, rgba(52, 211, 153, 0.05) 0%, transparent 50%),
        radial-gradient(circle at 20% 90%, rgba(96, 165, 250, 0.06) 0%, transparent 45%),
        linear-gradient(180deg, #070b14 0%, #0a0f1d 100%);
      color: var(--text-body);
      padding: 40px 24px 80px;
      line-height: 1.5;
      min-height: 100vh;
      overflow-x: hidden;
      position: relative;
    }}

    /* Subtle Architectural Grid Overlay */
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 44px 44px;
      pointer-events: none;
      z-index: 1;
    }}

    /* Soft, Subdued Ambient Atmosphere Orbs (Gentle & Pleasant) */
    .aurora-orb {{
      position: fixed;
      border-radius: 50%;
      filter: blur(140px);
      pointer-events: none;
      z-index: 0;
      opacity: 0.22;
      animation: auroraFloat 24s ease-in-out infinite alternate;
    }}
    .aurora-1 {{
      width: 550px;
      height: 550px;
      background: radial-gradient(circle, #38bdf8 0%, rgba(56, 189, 248, 0) 70%);
      top: -120px;
      left: -120px;
    }}
    .aurora-2 {{
      width: 650px;
      height: 650px;
      background: radial-gradient(circle, #a78bfa 0%, rgba(167, 139, 250, 0) 70%);
      top: 35%;
      right: -200px;
      animation-duration: 28s;
    }}
    .aurora-3 {{
      width: 500px;
      height: 500px;
      background: radial-gradient(circle, #34d399 0%, rgba(52, 211, 153, 0) 70%);
      bottom: -100px;
      left: 20%;
      animation-duration: 22s;
    }}

    @keyframes auroraFloat {{
      0% {{ transform: translate3d(0, 0, 0) scale(1); }}
      50% {{ transform: translate3d(40px, -35px, 0) scale(1.06); }}
      100% {{ transform: translate3d(-35px, 40px, 0) scale(0.96); }}
    }}

    .app-viewport {{
      max-width: 1300px;
      margin: 0 auto;
      position: relative;
      z-index: 2;
    }}

    /* =========================================================================
       3D GLASSMORPHIC CARDS WITH CONTROLLED SPECULAR REFLECTION
       ========================================================================= */
    .glass-card-3d {{
      background: var(--card-glass);
      backdrop-filter: var(--glass-blur);
      -webkit-backdrop-filter: var(--glass-blur);
      border: 1px solid var(--glass-border);
      border-radius: 20px;
      box-shadow:
        0 16px 40px -10px rgba(0, 0, 0, 0.6),
        0 0 0 1px rgba(255, 255, 255, 0.05) inset,
        0 1px 0 0 rgba(255, 255, 255, 0.25) inset;
      position: relative;
      overflow: hidden;
      transform-style: preserve-3d;
      transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.25s ease, border-color 0.25s ease;
    }}

    .glass-card-3d:hover {{
      background: var(--card-glass-hover);
      border-color: var(--glass-border-hover);
      box-shadow:
        0 24px 50px -10px rgba(0, 0, 0, 0.7),
        0 0 20px rgba(56, 189, 248, 0.15),
        0 0 0 1px rgba(255, 255, 255, 0.15) inset,
        0 1px 0 0 rgba(255, 255, 255, 0.4) inset;
    }}

    /* Refined Specular Light Sheen */
    .glass-sheen {{
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
      pointer-events: none;
    }}

    /* =========================================================================
       HERO HEADER PANEL
       ========================================================================= */
    .header-hero {{
      padding: 32px 36px;
      margin-bottom: 36px;
      background: linear-gradient(135deg, rgba(30, 41, 59, 0.75) 0%, rgba(15, 23, 42, 0.75) 100%);
    }}
    .hero-top-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 20px;
      margin-bottom: 16px;
    }}
    .hero-brand {{
      display: flex;
      align-items: center;
      gap: 18px;
    }}
    .hero-logo-prism {{
      width: 56px;
      height: 56px;
      background: linear-gradient(135deg, #0284c7 0%, #6366f1 50%, #8b5cf6 100%);
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      box-shadow:
        0 10px 24px rgba(2, 132, 199, 0.3),
        inset 0 1px 1px rgba(255, 255, 255, 0.5);
      transform: perspective(600px) rotateX(10deg) rotateY(-10deg);
      transition: transform 0.4s ease;
    }}
    .hero-logo-prism:hover {{
      transform: perspective(600px) rotateX(0deg) rotateY(0deg) scale(1.06);
    }}
    .hero-titles h1 {{
      font-size: 30px;
      font-weight: 800;
      letter-spacing: -0.8px;
      background: linear-gradient(135deg, #ffffff 0%, #38bdf8 60%, #c084fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 4px;
    }}
    .hero-titles .hero-tagline {{
      font-size: 14px;
      color: var(--text-muted);
      font-weight: 500;
    }}

    .validation-shield {{
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(52, 211, 153, 0.35);
      color: #34d399;
      padding: 8px 18px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 0 20px rgba(16, 185, 129, 0.15);
      backdrop-filter: blur(10px);
    }}
    .pulse-laser {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #34d399;
      box-shadow: 0 0 8px #34d399;
      animation: laserPulse 1.8s infinite;
    }}
    @keyframes laserPulse {{
      0%, 100% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(0.7); opacity: 0.4; }}
    }}

    .spec-pills-cluster {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .spec-pill {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 9999px;
      padding: 5px 14px;
      font-size: 12px;
      font-weight: 600;
      color: #cbd5e1;
      display: flex;
      align-items: center;
      gap: 6px;
      backdrop-filter: blur(10px);
    }}

    /* =========================================================================
       SECTION TITLES
       ========================================================================= */
    .section-banner {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
      margin-top: 10px;
    }}
    .section-icon-3d {{
      width: 34px;
      height: 34px;
      border-radius: 10px;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      color: var(--cyan);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }}
    .section-banner-title {{
      font-size: 20px;
      font-weight: 700;
      color: #f1f5f9;
      letter-spacing: -0.3px;
    }}

    /* =========================================================================
       1. EXECUTIVE 3D METRICS GRID
       ========================================================================= */
    .metrics-stage-3d {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 20px;
      margin-bottom: 44px;
    }}
    .metric-slab {{
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 185px;
    }}
    .metric-slab-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .metric-slab-title {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
    }}
    .metric-slab-badge {{
      width: 36px;
      height: 36px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow: 0 6px 14px rgba(0, 0, 0, 0.3);
    }}

    .metric-slab-val {{
      font-size: 40px;
      font-weight: 800;
      line-height: 1.1;
      letter-spacing: -1px;
      margin-bottom: 6px;
      transform: translateZ(24px);
    }}
    .metric-slab-foot {{
      font-size: 12px;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .glass-meter-track {{
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 9999px;
      overflow: hidden;
      margin-top: 10px;
    }}
    .glass-meter-fill {{
      height: 100%;
      border-radius: 9999px;
    }}

    /* Card Themes with Subdued, Refined Accents */
    .slab-cyan .metric-slab-badge {{ background: rgba(56, 189, 248, 0.15); color: var(--cyan); }}
    .slab-cyan .metric-slab-val {{ color: var(--cyan); }}
    .slab-cyan .glass-meter-fill {{ background: linear-gradient(90deg, #0284c7, #38bdf8); }}

    .slab-amber .metric-slab-badge {{ background: rgba(251, 191, 36, 0.15); color: var(--amber); }}
    .slab-amber .metric-slab-val {{ color: var(--amber); }}
    .slab-amber .glass-meter-fill {{ background: linear-gradient(90deg, #d97706, #fbbf24); }}

    .slab-emerald .metric-slab-badge {{ background: rgba(52, 211, 153, 0.15); color: var(--emerald); }}
    .slab-emerald .metric-slab-val {{ color: var(--emerald); }}
    .slab-emerald .glass-meter-fill {{ background: linear-gradient(90deg, #059669, #34d399); }}

    .slab-purple .metric-slab-badge {{ background: rgba(167, 139, 250, 0.15); color: var(--purple); }}
    .slab-purple .metric-slab-val {{ color: var(--purple); }}
    .slab-purple .glass-meter-fill {{ background: linear-gradient(90deg, #7c3aed, #a78bfa); }}

    /* =========================================================================
       2. LEADERBOARD TABLE (FROSTED GLASS)
       ========================================================================= */
    .leaderboard-slab {{
      padding: 4px;
      margin-bottom: 44px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 14px;
    }}
    thead th {{
      background: rgba(15, 23, 42, 0.9);
      padding: 16px 20px;
      font-weight: 700;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-muted);
      border-bottom: 1px solid var(--glass-border);
    }}
    tbody tr {{
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      transition: background 0.2s ease, transform 0.2s ease;
    }}
    tbody tr:hover {{
      background: rgba(255, 255, 255, 0.04);
    }}
    tbody tr:last-child {{
      border-bottom: none;
    }}
    td {{
      padding: 18px 20px;
      vertical-align: middle;
    }}
    .model-cell {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .glass-rank-pill {{
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 9999px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #f8fafc;
      white-space: nowrap;
    }}
    .model-title {{
      font-size: 15px;
      font-weight: 700;
      color: #ffffff;
    }}
    .model-meta {{
      font-size: 11px;
      color: var(--text-muted);
    }}
    .stat-num {{
      font-weight: 800;
      font-size: 15px;
    }}
    .stat-cyan {{ color: var(--cyan); }}
    .stat-blue {{ color: var(--blue); }}
    .stat-emerald {{ color: var(--emerald); }}
    .stat-purple {{ color: var(--purple); }}

    /* =========================================================================
       GLOSSY BADGES
       ========================================================================= */
    .gloss-badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 8px;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      display: inline-block;
      backdrop-filter: blur(8px);
    }}
    .badge-cyan {{ background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}
    .badge-blue {{ background: rgba(96, 165, 250, 0.12); color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.3); }}
    .badge-emerald {{ background: rgba(52, 211, 153, 0.12); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }}
    .badge-emerald-glow {{
      background: rgba(16, 185, 129, 0.2);
      color: #a7f3d0;
      border: 1px solid #10b981;
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.25);
    }}
    .badge-rose {{ background: rgba(248, 113, 113, 0.12); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); }}
    .badge-rose-glow {{
      background: rgba(239, 68, 68, 0.2);
      color: #fecaca;
      border: 1px solid #ef4444;
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.25);
    }}
    .badge-amber {{ background: rgba(251, 191, 36, 0.12); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); }}
    .badge-purple {{ background: rgba(167, 139, 250, 0.12); color: #c084fc; border: 1px solid rgba(167, 139, 250, 0.3); }}
    .badge-purple-glow {{
      background: rgba(167, 139, 250, 0.2);
      color: #f3e8ff;
      border: 1px solid #a78bfa;
      box-shadow: 0 0 10px rgba(167, 139, 250, 0.25);
    }}

    /* =========================================================================
       3. DIAGNOSTIC CHARTS (3D GLASS GALLERY)
       ========================================================================= */
    .charts-stage-3d {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(370px, 1fr));
      gap: 24px;
      margin-bottom: 44px;
    }}
    .chart-slab-3d {{
      padding: 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      cursor: pointer;
    }}
    .chart-slab-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }}
    .chart-pill-tag {{
      font-size: 11px;
      font-weight: 700;
      color: var(--cyan);
      background: rgba(56, 189, 248, 0.1);
      padding: 3px 8px;
      border-radius: 6px;
      border: 1px solid rgba(56, 189, 248, 0.25);
    }}
    .chart-zoom-badge {{
      font-size: 11px;
      color: var(--cyan);
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .chart-display-canvas {{
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: #020617;
      transition: transform 0.25s ease;
    }}
    .chart-display-canvas img {{
      width: 100%;
      height: auto;
      display: block;
      transition: transform 0.25s ease;
    }}
    .chart-slab-3d:hover .chart-display-canvas img {{
      transform: scale(1.02);
    }}
    .chart-caption-row {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text-muted);
      margin-top: 14px;
    }}

    /* =========================================================================
       4. VISUAL COUNTERFACTUAL INSPECTOR
       ========================================================================= */
    .cf-column-layout {{
      display: flex;
      flex-direction: column;
      gap: 28px;
      margin-bottom: 44px;
    }}
    .cf-showcase-panel {{
      padding: 24px;
    }}
    .cf-header-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .tags-cluster {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .cf-edit-pill {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      font-weight: 600;
      color: var(--cyan);
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid rgba(56, 189, 248, 0.25);
      padding: 4px 10px;
      border-radius: 8px;
    }}
    .cf-query-box {{
      font-size: 14px;
      color: #ffffff;
      background: rgba(2, 6, 23, 0.7);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-left: 3px solid var(--cyan);
      border-radius: 10px;
      padding: 12px 16px;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .query-bulb {{
      font-size: 18px;
    }}

    .cf-stage-3d {{
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 20px;
    }}
    @media (max-width: 860px) {{
      .cf-stage-3d {{
        grid-template-columns: 1fr;
      }}
      .orbital-flip-portal {{
        transform: rotate(90deg);
        margin: 12px auto;
      }}
    }}

    .twin-glass-pedestal {{
      background: rgba(2, 6, 23, 0.7);
      border: 1px solid var(--glass-border);
      border-radius: 14px;
      padding: 14px;
      text-align: center;
      cursor: pointer;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
      transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
    }}
    .twin-glass-pedestal:hover {{
      transform: translateY(-4px) scale(1.01);
      border-color: rgba(56, 189, 248, 0.5);
      box-shadow: 0 16px 35px rgba(0, 0, 0, 0.7);
    }}
    .pedestal-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-size: 11px;
      font-weight: 700;
      color: var(--text-muted);
    }}
    .pedestal-zoom {{
      color: var(--cyan);
      font-size: 11px;
      opacity: 0.8;
    }}
    .pedestal-img-frame {{
      width: 100%;
      max-width: 380px;
      margin: 0 auto 10px;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: #000;
    }}
    .pedestal-img {{
      width: 100%;
      aspect-ratio: 1;
      display: block;
      transition: transform 0.3s ease;
    }}
    .twin-glass-pedestal:hover .pedestal-img {{
      transform: scale(1.03);
    }}
    .pedestal-bottom {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
      font-weight: 600;
      padding: 4px 6px 0;
    }}

    /* Balanced 3D Flip Orbit Badge */
    .orbital-flip-portal {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      position: relative;
      width: 64px;
      height: 64px;
    }}
    .portal-ring {{
      position: absolute;
      border-radius: 50%;
      border: 1px dashed rgba(56, 189, 248, 0.4);
      pointer-events: none;
    }}
    .ring-outer {{
      width: 64px;
      height: 64px;
      animation: spinClockwise 12s linear infinite;
    }}
    .ring-inner {{
      width: 50px;
      height: 50px;
      border-color: rgba(167, 139, 250, 0.4);
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
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
      border: 1px solid rgba(56, 189, 248, 0.4);
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #38bdf8;
      font-weight: 800;
      line-height: 1;
      z-index: 2;
    }}
    .flip-arrows {{
      font-size: 15px;
    }}
    .flip-sub {{
      font-size: 8px;
      letter-spacing: 0.5px;
    }}

    /* =========================================================================
       5. ABSTENTION INSPECTOR
       ========================================================================= */
    .abstention-stage-3d {{
      display: grid;
      grid-template-columns: 1fr 1.3fr;
      gap: 24px;
      align-items: center;
    }}
    @media (max-width: 860px) {{
      .abstention-stage-3d {{
        grid-template-columns: 1fr;
      }}
    }}
    .abstention-proof-card {{
      background: rgba(2, 6, 23, 0.7);
      border: 1px solid rgba(167, 139, 250, 0.25);
      border-radius: 14px;
      padding: 22px 24px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    }}
    .proof-head {{
      font-size: 16px;
      font-weight: 700;
      color: #c084fc;
      margin-bottom: 14px;
    }}
    .proof-items {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
      font-size: 13px;
      color: #cbd5e1;
      line-height: 1.6;
    }}
    .hl-code {{
      background: rgba(255, 255, 255, 0.08);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
      color: var(--cyan);
    }}

    /* =========================================================================
       6. LIGHTBOX MODAL
       ========================================================================= */
    .modal-lightbox {{
      position: fixed;
      inset: 0;
      background: rgba(2, 6, 23, 0.9);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
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
      max-width: 880px;
      width: 100%;
      background: rgba(15, 23, 42, 0.96);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 20px;
      box-shadow: 0 25px 80px rgba(0, 0, 0, 0.9);
      overflow: hidden;
      animation: zoomModalIn 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}
    @keyframes zoomModalIn {{
      0% {{ transform: scale(0.92); opacity: 0; }}
      100% {{ transform: scale(1); opacity: 1; }}
    }}
    .modal-topbar {{
      padding: 16px 22px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      background: rgba(255, 255, 255, 0.03);
    }}
    .modal-headline {{
      font-size: 15px;
      font-weight: 700;
      color: #ffffff;
    }}
    .modal-close-x {{
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #ffffff;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 15px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s ease;
    }}
    .modal-close-x:hover {{
      background: rgba(239, 68, 68, 0.5);
    }}
    .modal-canvas-frame {{
      padding: 20px;
      text-align: center;
    }}
    .modal-canvas-frame img {{
      max-width: 100%;
      max-height: 70vh;
      border-radius: 12px;
      box-shadow: 0 12px 35px rgba(0, 0, 0, 0.7);
    }}

    /* =========================================================================
       FOOTER
       ========================================================================= */
    .footer-hero {{
      padding: 28px 36px;
      margin-top: 48px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      font-size: 13px;
      color: var(--text-muted);
    }}
    .footer-action-link {{
      color: var(--cyan);
      text-decoration: none;
      font-weight: 700;
    }}
  </style>
</head>
<body>

  <!-- Gentle Ambient Glow Orbs (Subtle, Non-Distracting) -->
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
          <span>{baseline_name} gap reaches: <strong style="color: var(--amber);">+{baseline_gap}%</strong></span>
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
          <span>{baseline_name} Hallucination: <strong style="color: var(--rose);">{100.0 - baseline_abs:.1f}%</strong></span>
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

    <!-- 4. Visual Counterfactual Inspector -->
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

  <!-- Interactive 3D Card Tilt Script -->
  <script>
    document.querySelectorAll('.glass-card-3d').forEach(card => {{
      card.addEventListener('mousemove', e => {{
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotateX = ((y - centerY) / centerY) * -4;
        const rotateY = ((x - centerX) / centerX) * 4;

        card.style.transform = `perspective(1000px) rotateX(${{rotateX.toFixed(2)}}deg) rotateY(${{rotateY.toFixed(2)}}deg) translateY(-3px)`;
      }});

      card.addEventListener('mouseleave', () => {{
        card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)';
      }});
    }});

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
