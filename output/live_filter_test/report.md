# Visual Task Factory: Milestone 3 Benchmark Evaluation Report
*Generated on: 2026-11-22 10:55:18*

## 1. Executive Summary & Model Leaderboard

| Model | Open-Ended Acc | MCQ Acc | MCQ Shortcut Gap | Pairwise Consistency | Abstention Acc | Hallucination Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **mock-frontier-mid** | 56.7% | 66.7% | +10.0% | 50.0% | 50.0% | 50.0% |
| **mock-frontier-strong** | 80.0% | 100.0% | +20.0% | 50.0% | 83.3% | 16.7% |

## 2. Accuracy by Difficulty Tier

| Model | Easy Tier | Medium Tier | Hard Tier |
| :--- | :---: | :---: | :---: |
| **mock-frontier-mid** | 73.3% | 66.7% | 0.0% |
| **mock-frontier-strong** | 93.3% | 66.7% | 66.7% |

## 3. Shapely Occlusion Sensitivity Curve

| Model | 0% - 25% Occlusion | 25% - 50% Occlusion | 50% - 75% Occlusion | 75% - 100% Occlusion |
| :--- | :---: | :---: | :---: | :---: |
| **mock-frontier-mid** | 50.0% | 75.0% | 0.0% | 50.0% |
| **mock-frontier-strong** | 68.8% | 100.0% | 0.0% | 83.3% |

## 4. Key Findings & Diagnostic Observations

1. **MCQ Shortcut Gap:** Models exhibit higher accuracy on multiple-choice questions compared to open-ended generation, reflecting guessing and process-of-elimination heuristics.
2. **Pairwise Consistency:** Evaluating counterfactual twins reveals that weaker models often solve one twin while failing its flipped twin, exposing brittle pattern matching rather than true spatial grounding.
3. **Abstention Reliability:** On 100% occluded targets (`cannot_determine`), models with lower abstention accuracy hallucinate shape and color attributes instead of acknowledging lack of visual information.
4. **Occlusion Degradation:** Dense technical overlaps produce steep degradation curves as multi-layer occlusions conceal shape boundaries.

## 5. Diagnostic Charts

- `charts/accuracy_by_difficulty.png`
- `charts/consistency_and_mcq_gap.png`
- `charts/occlusion_dropoff.png`
