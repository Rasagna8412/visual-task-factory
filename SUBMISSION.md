# Innodata AI Hackathon — Track 2: Visual Task Factory
## Official Submission Kit & Grand Finale Pitch Guide

**Team:** Rasagna & Team  
**Track:** Track 2 — Visual Task Factory  
**Repository:** [https://github.com/Rasagna8412/visual-task-factory](https://github.com/Rasagna8412/visual-task-factory)  
**Live Demo Dashboard:** [`output/final_live_run/dashboard.html`](output/final_live_run/dashboard.html)  

---

## 1. Hack2skill Final Submission Summary (Copy-Paste Ready)

### **Project Title:**
**Visual Task Factory: Procedural 2D Spatial Occlusion, Multi-Layer Depth Reasoning & Counterfactual Benchmark for Frontier VLMs**

### **Executive Overview:**
Visual Task Factory is an automated, deterministic visual benchmark generator and multi-VLM evaluation factory built specifically for Track 2 of the Innodata AI Hackathon. 

Rather than relying on static academic datasets or diffusion models (which hallucinate geometry and produce noisy, unreliable labels), Visual Task Factory procedurally constructs dense 2D technical diagrams using vanilla HTML5/SVG and computes mathematically exact ground truth via planar Shapely polygon geometry. Scenes are batch-rendered at $1024 \times 1024$ resolution using a single headless Playwright Chromium instance (~0.15s per image) and audited through a two-stage automated validation gate before benchmarking.

---

## 2. Innodata Scoring Rubric Mapping (100% Score Alignment)

| Rubric Dimension | Weight | Our Implementation & Evidence |
| :--- | :---: | :--- |
| **Implementation & Repeatability** | **25%** | • **100% Deterministic:** Every scene, query, and distractor is derived from an explicit integer `seed` and difficulty matrix.<br>• **Single-Command CLI:** Full pipeline executes via `python main.py` or `--eval-only`.<br>• **Fast Batch Rendering:** Single persistent Playwright browser renders 30 images in ~4.5 seconds.<br>• **Zero Flakiness:** Exact Boolean 2D geometry guarantees bit-for-bit label fidelity. |
| **Validity & Validation Evidence** | **25%** | • **Shapely Visibility Audit:** Rejects any shape with visible area ratio $< 0.10$ or $> 0.90$, or outside $[0, 1024]$ bounds.<br>• **Live Anti-Shortcut Filter:** Transmits text-only questions (no image) to local Ollama (`dolphin3:8b`) across 3 trials. Rejects tasks where blind LLMs guess above random chance.<br>• **Atomic Pair Dropping:** If either twin in a pair leaks, both are dropped.<br>• **Proven Evidence:** **29 / 38 tasks passed (76.3%)**; 9 leaky tasks rejected. |
| **Meaningful Variation** | **20%** | • **Orthogonal Difficulty Axes:** Configurable matrix varying node density (10–52 nodes), occlusion ratios, and distractor gridlines.<br>• **Multi-Shape Geometries:** Circles, squares, equilateral triangles with varied aspect ratios.<br>• **Layered Depth Graphs:** Full bidirectional occlusion graphs (`occluding`, `occluded_by`) across 4 z-depth tiers. |
| **Original Approach & Engineering Judgment** | **15%** | • **Counterfactual Image Twins:** Paired scenes differing by exactly one surgical z-order swap (>95% pixel identity) where the ground-truth answer inverts.<br>• **Pairwise Consistency Metric:** Evaluates whether models truly perceive depth ordering (correct on both twins).<br>• **Abstention Mode:** 100% occluded targets (`visible_area == 0.0`) expecting `"cannot_determine"` to measure visual hallucination rates. |
| **Practical Impact & Communication** | **15%** | • **348 Live Vision Queries:** Evaluated real local VLMs (`qwen2.5vl:3b` and `moondream`) via Ollama with zero mock data.<br>• **Interactive 3D Glassmorphic Dashboard:** Self-contained portable `dashboard.html` with specular tilt, leaderboard, and lightbox.<br>• **Publication Charts:** 300 DPI Matplotlib degradation and occlusion sensitivity curves. |

---

## 3. Real Benchmark Leaderboard (Seed 42 — 348 Live Vision Queries)

We evaluated 348 live vision queries (29 certified clean tasks $\times$ 3 questions $\times$ 2 modalities) across local vision models on a single consumer laptop without cloud GPUs:

```
================================================================================================================
                                   OFFICIAL BENCHMARK LEADERBOARD
================================================================================================================
Model          | Open-Ended Acc | MCQ Acc | MCQ Shortcut Gap | Pairwise Consistency | Abstention Acc | Hallucination
----------------------------------------------------------------------------------------------------------------
qwen2.5vl-3b   |     35.6%      |  40.2%  |     +4.6%        |         0.0%         |     46.7%      |    53.3%
moondream      |      0.0%      |  35.6%  |    +35.6%        |         0.0%         |      0.0%      |   100.0%
================================================================================================================
```

### **Critical Findings from Live Data:**
1. **The MCQ Shortcut Illusion (+35.6% Gap):**
   `moondream` failed every open-ended visual counting question (**0.0%**), yet scored **35.6%** on 4-option multiple choice. Standard benchmarks relying exclusively on MCQs drastically overestimate multimodal reasoning due to random guessing and elimination heuristics.
2. **Brittle Depth Grounding (0.0% Pairwise Consistency):**
   Neither model achieved consistent correctness across both halves of any counterfactual pair. When a shape's z-order was swapped, models failed to invert their answers, proving they rely on superficial global texture rather than localized occlusion reasoning.
3. **Severe Hallucination on Hidden Nodes:**
   On 100% occluded targets (`cannot_determine`), `moondream` hallucinated **100.0%** of the time, inventing colors and shapes for geometry that was completely hidden. `qwen2.5vl:3b` correctly abstained **46.7%** of the time.

---

## 4. 5-Minute Demo Day Pitch Script & Slide Outline (Grand Finale — New Delhi)

### **Slide 1: Title & The Core Problem (0:00 – 1:00)**
- **Title:** Visual Task Factory: Unmasking VLM Hallucination & Guessing with Procedural Geometry
- **Speaker:** "Good morning, judges. Current multimodal benchmarks suffer from three fatal flaws: diffusion-generated images have noisy labels, multiple-choice questions reward lucky guessing, and static benchmarks leak into LLM pretraining data. We built the Visual Task Factory—a deterministic, code-driven benchmark engine that programmatically constructs dense technical diagrams with mathematically exact Shapely geometry."

### **Slide 2: Pipeline Architecture & Validation Gate (1:00 – 2:00)**
- **Visual:** 6-Stage Pipeline Diagram + Validation Gate pass rate (76.3%).
- **Speaker:** "Every task is built with vanilla SVG/HTML5 and rendered at $1024 \times 1024$ in 0.15s via Playwright. But generation is only half the battle. Before any task enters our benchmark, it must survive our two-stage Automated Validation Gate:
  1. A Shapely clipping and visibility audit ensuring all target shapes have between 10% and 90% visible area.
  2. A live blind text-only LLM filter using local Ollama `dolphin3:8b`. If a blind model can guess the answer from prompt phrasing alone, the task is rejected. In our live run, this gate caught 9 leaky tasks, certifying 29 clean tasks."

### **Slide 3: Advanced Evaluation Primitives (2:00 – 3:15)**
- **Visual:** Side-by-side Base vs. Counterfactual Twin with flipped ground truth + Abstention diagram.
- **Speaker:** "We introduce three novel evaluation primitives:
  - **Counterfactual Image Twins:** Paired scenes that are $>95\%$ pixel-identical with a single surgical z-order swap. We evaluate **Pairwise Consistency**—a model only gets credit if it answers *both* twins correctly.
  - **Dual-Modality Evaluation:** Every question is tested in Open-Ended and 4-Option MCQ to measure the exact **MCQ Shortcut Gap**.
  - **Abstention Testing:** We insert 100% occluded hidden targets. The only correct answer is `cannot_determine`. Any shape or color response is penalized as an outright hallucination."

### **Slide 4: Live Results & Diagnostic Insights (3:15 – 4:15)**
- **Visual:** Leaderboard + 300 DPI Matplotlib Failure Curves.
- **Speaker:** "Here are our real, non-mocked results across 348 live vision queries on `qwen2.5vl:3b` and `moondream`:
  - `moondream` had a massive **+35.6% MCQ gap**—scoring 0% on open-ended questions but 35.6% on MCQ.
  - Both models scored **0.0% Pairwise Consistency** across all 12 counterfactual pairs, demonstrating that today's lightweight VLMs lack true 3D spatial grounding.
  - On hidden nodes, `moondream` hallucinated 100% of the time, while `qwen2.5vl:3b` correctly abstained 46.7% of the time."

### **Slide 5: Live Demo & Impact (4:15 – 5:00)**
- **Visual:** Screen display of our self-contained, 3D glassmorphic `dashboard.html`.
- **Speaker:** "Everything is packaged into a self-contained 3D glassmorphic dashboard with interactive tilt, full-screen lightbox inspection, and exportable JSON metrics. It runs in 5 minutes via a single command, supports plug-and-play frontier APIs like GPT-4o, Gemini 1.5 Pro, and Claude 3.5 Sonnet, and gives benchmark creators an uncheatable, reproducible testbed. Thank you!"

---

## 5. Quick Reproduction Guide for Judges

```powershell
# 1. Clone & Setup
git clone https://github.com/Rasagna8412/visual-task-factory.git
cd visual-task-factory
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\playwright.exe install chromium

# 2. Fast Re-Evaluation of Pre-Validated Live Run (~2 minutes)
.venv\Scripts\python.exe main.py --eval-only --output output/final_live_run --models qwen2.5vl-3b,moondream

# 3. Full End-to-End Pipeline from Scratch (Seed 42)
.venv\Scripts\python.exe main.py --pairs 16 --abstentions 6 --seed 42 --models qwen2.5vl-3b,moondream --output output/final_live_run

# 4. Zero-Cost Mock Run (for laptops without Ollama installed)
.venv\Scripts\python.exe main.py --pairs 12 --abstentions 6 --seed 42 --mock-ollama --mock-vlm --output output/run_42
```
