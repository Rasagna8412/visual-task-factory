# Visual Task Factory: Milestone 3 Benchmark Evaluation Report
*Generated on: 2026-11-22 16:25:54*

## 1. Executive Summary & Model Leaderboard

| Model | Open-Ended Acc | MCQ Acc | MCQ Shortcut Gap | Pairwise Consistency | Abstention Acc | Hallucination Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **moondream** | 0.0% | 35.6% | +35.6% | 0.0% | 0.0% | 100.0% |
| **qwen2.5vl-3b** | 35.6% | 40.2% | +4.6% | 0.0% | 46.7% | 53.3% |

## 2. Accuracy by Difficulty Tier

| Model | Easy Tier | Medium Tier | Hard Tier |
| :--- | :---: | :---: | :---: |
| **moondream** | 0.0% | 0.0% | 0.0% |
| **qwen2.5vl-3b** | 50.0% | 33.3% | 23.3% |

## 3. Shapely Occlusion Sensitivity Curve

| Model | 0% - 25% Occlusion | 25% - 50% Occlusion | 50% - 75% Occlusion | 75% - 100% Occlusion |
| :--- | :---: | :---: | :---: | :---: |
| **moondream** | 0.0% | 0.0% | 0.0% | 0.0% |
| **qwen2.5vl-3b** | 44.1% | 21.9% | 33.3% | 46.7% |

## 4. Key Findings & Diagnostic Observations

1. **MCQ Shortcut Gap:** Models exhibit higher accuracy on multiple-choice questions compared to open-ended generation, reflecting guessing and process-of-elimination heuristics.
2. **Pairwise Consistency:** Evaluating counterfactual twins reveals that weaker models often solve one twin while failing its flipped twin, exposing brittle pattern matching rather than true spatial grounding.
3. **Abstention Reliability:** On 100% occluded targets (`cannot_determine`), models with lower abstention accuracy hallucinate shape and color attributes instead of acknowledging lack of visual information.
4. **Occlusion Degradation:** Dense technical overlaps produce steep degradation curves as multi-layer occlusions conceal shape boundaries.

## 5. Diagnostic Charts

- `charts/accuracy_by_difficulty.png`
- `charts/consistency_and_mcq_gap.png`
- `charts/occlusion_dropoff.png`
