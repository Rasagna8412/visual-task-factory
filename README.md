# Visual Task Factory: 2D Spatial Occlusion & Counting Benchmark

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Playwright Chromium](https://img.shields.io/badge/playwright-chromium-green.svg)](https://playwright.dev/)
[![Shapely Geometry](https://img.shields.io/badge/shapely-exact%20geometry-brightgreen.svg)](https://shapely.readthedocs.io/)
[![Validation Gate](https://img.shields.io/badge/validation%20gate-76.3%25%20passed%20(29%2F38)-success.svg)](#3-live-benchmark-results-seed-42--348-vision-queries)
[![Live Queries](https://img.shields.io/badge/live%20eval-348%20vision%20queries-blueviolet.svg)](#3-live-benchmark-results-seed-42--348-vision-queries)

A deterministic benchmark generation engine and evaluation suite designed to probe **2D Spatial Occlusion, Multi-Layer Depth Reasoning, and Counting** in Vision-Language Models (VLMs) on dense technical diagrams.

Built for the **InnoData Visual Reasoning Benchmark Hackathon**.

---

## 1. System Architecture

```
                                 VISUAL TASK FACTORY PIPELINE
                                 
   [Root Seed & Difficulty Matrix]
                 │
                 ▼
  ┌───────────────────────────────┐
  │  Stage 1: Scene Builder       │  ──> Exact Shapely Polygons (Circles, Squares, Triangles)
  │  (generator/scene_builder.py) │  ──> Counterfactual Twins (z-order swapped, >95% pixel identity)
  │                               │  ──> Abstention Targets (100% occluded hidden nodes)
  └──────────────┬────────────────┘
                 │ (scene.html + ground_truth.json)
                 ▼
  ┌───────────────────────────────┐
  │  Stage 2: High-Speed Renderer │  ──> SINGLE Headless Playwright Chromium Browser Instance
  │  (renderer/capture.py)        │  ──> 1024x1024 PNG Capture (~0.15s / image)
  └──────────────┬────────────────┘
                 │ (scene.png)
                 ▼
  ┌───────────────────────────────┐
  │  Stage 3: Validation Gate     │  ──> [1] Viewport Clipping & Visibility Check (0.10 - 0.90 ratio)
  │  (validator/)                 │  ──> [2] Text-Only LLM Shortcut Filter (Ollama dolphin3:8b)
  │                               │  ──> [3] Atomic Pair Filtering (drops orphaned counterfactual twins)
  └──────────────┬────────────────┘
                 │ (Verified Clean Benchmark Tasks: 29 / 38 passed = 76.3%)
                 ▼
  ┌───────────────────────────────┐
  │  Stage 4: Multi-VLM Evaluator │  ──> Open-Ended vs. 4-Option MCQ Modalities
  │  (benchmark/evaluator.py)     │  ──> Live Vision Models: qwen2.5vl:3b, moondream (via Ollama)
  │                               │  ──> Frontier VLM APIs (OpenAI, Gemini, Claude, Custom Gateway)
  │                               │  ──> Zero-Cost Simulated Profiles (mock-frontier-strong/mid)
  └──────────────┬────────────────┘
                 │ (raw_results.json — 348 Live Vision Queries)
                 ▼
  ┌───────────────────────────────┐
  │  Stage 5: Reporting & Charts  │  ──> 3 Diagnostic Charts (300 DPI Matplotlib)
  │  (benchmark/report_generator) │  ──> benchmark_summary.json + report.md Leaderboard
  └──────────────┬────────────────┘
                 │
                 ▼
  ┌───────────────────────────────┐
  │  Stage 6: Demo Day Dashboard  │  ──> Self-Contained dashboard.html with Visual Counterfactual
  │  (benchmark/dashboard_builder)│      Inspector & Interactive Metric Cards
  └───────────────────────────────┘
```

---

## 2. Innodata Judging Criteria Alignment

### I. Technical Depth & Ground Truth Precision
- **Exact Vector Geometry:** Never relies on diffusion models or approximate pixel heuristics. Every scene is constructed programmatically with vanilla SVG/HTML5 and computed via **Shapely exact 2D polygon math**.
- **Exact Occlusion Computation:** Calculates precise planar intersections and Boolean differences (`geom_i.difference(higher_geoms_union)`), yielding mathematical occlusion ratios, exact visible areas, and bidirectional occlusion graphs (`occluded_by`, `occluding`).
- **Painter's Algorithm Fidelity:** SVG z-order strictly aligns with rendering order, guaranteeing ground truth matches visual rasterization byte-for-byte.

### II. Evaluation Rigor & Automated Validation Gate
Every generated task must pass a strict two-stage automated gate before entering the benchmark set:
1. **Viewport Clipping & Visibility Audit (`validator/visibility_check.py`):**
   - Asserts all bounding boxes fall strictly within $[0, 1024]$.
   - Validates that partially occluded shapes possess a visible ratio between **0.10 and 0.90** (rejecting shapes that are either imperceptible slivers or barely touched).
2. **Text-Only LLM Shortcut Filter (`validator/shortcut_filter.py`):**
   - Transmits question text **without the image** to local Ollama (`dolphin3:8b`) across independent trials.
   - Automatically rejects questions where language priors or prompt cues allow a blind text-only model to guess the exact answer above chance.
3. **Atomic Pair Filtering:** If either twin in a counterfactual pair fails validation, **both twins are dropped atomically**, ensuring Pairwise Consistency is never measured on orphaned halves.

### III. Advanced Evaluation Primitives
- **Counterfactual Image Twins:** Generates `base` and `counterfactual` pairs from the same seed that differ by exactly **one surgical edit** (swapping the z-order of two overlapping shapes). The visual scene is $>95\%$ pixel-identical while the ground truth answer flips (e.g. `"yes"` $\leftrightarrow$ `"no"`).
- **Pairwise Consistency Metric:** Evaluates whether a model genuinely understands depth ordering. A counterfactual pair is only credited as correct if the model answers **both** the base and counterfactual twins correctly.
- **Abstention Reliability & Hallucination Rate:** Features an `unanswerable` mode where a queried shape is 100% occluded by a larger foreground shape (`visible_area == 0.0`). The only correct response is `"cannot_determine"`. Models that guess a shape or color are penalized for visual hallucination.
- **MCQ Shortcut Gap:** Measures the performance discrepancy between open-ended generation and 4-option multiple choice ($\text{Acc}_{\text{mcq}} - \text{Acc}_{\text{open}}$), exposing guessing artifacts and process-of-elimination heuristics.

### IV. Performance, Scalability & Reproducibility
- **Pure Determinism:** Given an explicit integer `--seed`, the entire pipeline reproduces the exact same SVG layouts, PNG renders, ground truths, and evaluation decisions.
- **Browser Instance Reuse:** Renders batch PNGs using **one single headless Playwright Chromium instance** across the entire batch render phase (~0.15s per 1024x1024 image), never launching/closing browsers per image.
- **Zero-Cost Simulation:** Bundles two realistic simulated profiles (`mock-frontier-strong` and `mock-frontier-mid`) modeling difficulty drop-off, occlusion sensitivity curves, and MCQ gaps without requiring external API credits.

### V. Actionable Reporting & Demo Day Dashboard
- **Diagnostic Charts (300 DPI):**
  1. `charts/accuracy_by_difficulty.png` (Easy vs. Medium vs. Hard degradation).
  2. `charts/consistency_and_mcq_gap.png` (Open-Ended vs. MCQ vs. Pairwise Consistency vs. Abstention).
  3. `charts/occlusion_dropoff.png` (Performance plotted against exact Shapely occlusion ratio buckets).
- **Interactive HTML Dashboard (`dashboard.html`):** Self-contained, portable single-file dashboard featuring executive metric cards, embedded high-res diagnostic charts, and a side-by-side **Visual Counterfactual Inspector**.

---

## 3. Live Benchmark Results (Seed 42 — 348 Vision Queries)

We conducted a full live, non-mocked evaluation on **348 vision queries** using local Vision-Language Models (`qwen2.5vl:3b` and `moondream`) served via Ollama.

All generated data, raw query outputs, 300 DPI publication charts, markdown reports, and interactive dashboards from this run are tracked directly in [`output/final_live_run/`](file:///c:/Users/LOQ/OneDrive/Desktop/visual-task-factory/output/final_live_run/).

### Validation Gate Execution Stats (Live Ollama `dolphin3:8b`)
- **Total Initial Tasks:** 38 tasks (16 counterfactual pairs = 32 twins + 6 abstention tasks)
- **Validation Gate Results:** **29 / 38 tasks passed (76.3%)**
- **Rejections:** 9 tasks rejected (blind text-only shortcut leakage detected on language priors + atomic pruning of orphaned counterfactual twins).
- **Final Benchmark Set:** 29 certified clean visual reasoning tasks (12 counterfactual pairs + 5 abstentions).
- **Evaluation Load:** 29 tasks $\times$ 3 questions $\times$ 2 formats (Open-Ended + MCQ) = **174 queries per model** $\times$ 2 models = **348 total live vision queries**.

### Official Model Leaderboard

| Model | Open-Ended Acc | MCQ Acc | MCQ Shortcut Gap | Pairwise Consistency | Abstention Acc | Hallucination Rate | Queries Evaluated |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`qwen2.5vl-3b`** | **35.6%** | **40.2%** | **+4.6%** | **0.0%** | **46.7%** | **53.3%** | 174 |
| **`moondream`** | **0.0%** | **35.6%** | **+35.6%** | **0.0%** | **0.0%** | **100.0%** | 174 |

### Accuracy by Difficulty Tier

| Model | Easy Tier | Medium Tier | Hard Tier |
| :--- | :---: | :---: | :---: |
| **`qwen2.5vl-3b`** | **50.0%** | **33.3%** | **23.3%** |
| **`moondream`** | **0.0%** | **0.0%** | **0.0%** |

### Accuracy by Shapely Occlusion Ratio Bucket

| Model | 0% – 25% Occlusion | 25% – 50% Occlusion | 50% – 75% Occlusion | 75% – 100% Occlusion |
| :--- | :---: | :---: | :---: | :---: |
| **`qwen2.5vl-3b`** | **44.1%** | **21.9%** | **33.3%** | **46.7%** |
| **`moondream`** | **0.0%** | **0.0%** | **0.0%** | **0.0%** |

### Key Diagnostic Observations from Live Data:
1. **The Moondream MCQ Illusion (+35.6% Gap):** `moondream` scored **0.0%** in open-ended visual generation (failing exact counting and geometric depth questions), but leaped to **35.6%** on 4-option MCQs. Standard MCQ-only visual benchmarks would dramatically overstate this model's reasoning capacity.
2. **Brittle Depth Grounding (0.0% Pairwise Consistency):** Across 12 counterfactual pairs, neither `qwen2.5vl-3b` nor `moondream` achieved consistent correctness on both twins of any pair. When a shape's z-order was flipped, the models failed to flip their answer, proving they rely on global visual patterns rather than true local occlusion reasoning.
3. **Severe Hallucination on Hidden Nodes:** On 100% occluded targets (`cannot_determine`), `moondream` hallucinated **100.0%** of the time, inventing colors and shapes for geometry that was completely hidden. `qwen2.5vl-3b` correctly abstained on **46.7%** of hidden targets, hallucinating on the remaining **53.3%**.
4. **Difficulty Degradation:** `qwen2.5vl-3b` showed a textbook monotonic decline from **50.0%** on Easy diagrams down to **23.3%** on Hard diagrams as node density and distractor gridlines multiplied.

---

## 4. Quickstart & Single-Command Reproduction

### Installation

```powershell
# Clone workspace & enter directory
git clone https://github.com/your-username/visual-task-factory.git
cd visual-task-factory

# Create virtual environment & install dependencies
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\playwright.exe install chromium
```

### Command 1: Reproduce Live Benchmark from Scratch (Seed 42)

Runs the complete 6-stage end-to-end pipeline: generates deterministic scenes, batch renders PNGs via Playwright, executes live Ollama validation, runs live vision models, computes metrics, and builds the HTML dashboard:

```powershell
.venv\Scripts\python.exe main.py --pairs 16 --abstentions 6 --seed 42 --models qwen2.5vl-3b,moondream --output output/final_live_run
```

### Command 2: Instant Fast Re-Evaluation (`--eval-only`)

Skips scene generation, rendering, and validation gates by directly loading the certified clean dataset from `output/final_live_run/` to re-run vision evaluation, chart rendering, and dashboard compilation in minutes:

```powershell
.venv\Scripts\python.exe main.py --eval-only --output output/final_live_run --models qwen2.5vl-3b,moondream
```

### Command 3: Zero-Cost Fast Mock Run (Zero API / Ollama Overhead)

For instant verification on any laptop without downloading Ollama models or using API credits:

```powershell
.venv\Scripts\python.exe main.py --pairs 12 --abstentions 6 --seed 42 --mock-ollama --mock-vlm --output output/run_42
```

Inspect the generated artifacts:
- `output/run_42/dashboard.html` (Demo Day visual dashboard)
- `output/run_42/report.md` (Leaderboard and findings)
- `output/run_42/benchmark_summary.json` (Structured metrics)
- `output/run_42/raw_results.json` (Raw VLM responses and grading logs)
- `output/run_42/charts/` (300 DPI publication diagnostic charts)

---

## 5. Frontier VLM API Integration

To evaluate frontier commercial models (OpenAI, Gemini, Anthropic, or InnoData custom gateway), copy `.env.example` to `.env` and set your credentials:

```powershell
cp .env.example .env
```

Edit `.env`:
```env
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
ANTHROPIC_API_KEY=sk-ant-...
CUSTOM_VLM_BASE_URL=https://api.openai.com/v1
CUSTOM_VLM_API_KEY=sk-custom-...
```

Then execute `main.py` targeting your desired models from `config/models.json`:

```powershell
.venv\Scripts\python.exe main.py --pairs 12 --abstentions 6 --seed 42 --models gpt-4o,gemini-1.5-pro,claude-3-5-sonnet
```

---

## 6. Directory Layout

```
visual-task-factory/
├── AGENTS.md                   # Operational rules & benchmark guidelines
├── README.md                   # Complete documentation & judge guide
├── requirements.txt            # Python dependencies
├── .env.example                # API credentials template
├── .gitignore                  # Submission gitignore (tracks final_live_run, ignores temp caches)
├── main.py                     # Single-command production CLI entry point
├── smoke_test.py               # Milestone 2 end-to-end smoke test
├── benchmark_smoke_test.py     # Milestone 3 benchmark smoke test
├── config/
│   ├── difficulty_matrix.json  # Easy / Medium / Hard tier parameters
│   └── models.json             # VLM endpoints & provider registry
├── generator/
│   ├── __init__.py
│   └── scene_builder.py        # Shapely exact vector generator & counterfactuals
├── renderer/
│   ├── __init__.py
│   └── capture.py              # Single-instance Playwright batch renderer
├── validator/
│   ├── __init__.py
│   ├── visibility_check.py     # Bounding box & Shapely visibility auditor
│   └── shortcut_filter.py      # Local Ollama text-only anti-shortcut filter
├── benchmark/
│   ├── __init__.py
│   ├── vlm_client.py           # Multi-provider async VLM client & 512x512 token optimizer
│   ├── evaluator.py            # Scoring engine & pairwise metric aggregator
│   ├── report_generator.py     # 300 DPI Matplotlib diagnostic chart generator
│   └── dashboard_builder.py    # Self-contained Demo Day HTML dashboard
└── output/
    └── final_live_run/         # TRACKED LIVE BENCHMARK SUBMISSION ARTIFACTS
        ├── dataset/            # 29 validated task directories (HTML, JSON, PNG)
        ├── charts/             # 3 publication-grade 300 DPI PNG charts
        │   ├── accuracy_by_difficulty.png
        │   ├── consistency_and_mcq_gap.png
        │   └── occlusion_dropoff.png
        ├── dashboard.html      # Interactive Demo Day HTML Dashboard
        ├── report.md           # Markdown executive summary & leaderboard
        ├── benchmark_summary.json # Machine-readable benchmark summary
        └── raw_results.json    # Complete audit log of 348 live vision queries
```
