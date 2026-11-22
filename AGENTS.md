# Visual Task Factory Rules
- **Determinism:** Every scene must be generated from an explicit integer `seed` and difficulty config so the exact same PNG and `ground_truth.json` can be reproduced.
- **Exact Ground Truth:** Never use diffusion models. Generate scenes programmatically (vanilla HTML5/CSS3/SVG/Canvas) and export exact ground truth (counts, coordinates, labels, bounding boxes) in the same pass.
- **Performance:** Always reuse a single headless Playwright Chromium browser instance across batch renders. Never launch/close a browser per image.
- **Validation Gate:** Every generated task must pass (1) a bounding-box visibility/clipping check and (2) a text-only LLM shortcut filter (local Ollama or API) before entering the benchmark set.
- **Verification:** After modifying any module, run a 5-sample end-to-end smoke test via CLI before finishing the turn.
