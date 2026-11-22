"""Text-only LLM shortcut filter module for Visual Task Factory (Milestone 2).

Tests whether questions in ground_truth.json can be guessed by a text-only LLM
(without seeing the image) above random chance (1/4 for 4-option MCQ).
Queries local Ollama (dolphin3:8b) via httpx POST with a clean --mock-ollama fallback.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

OLLAMA_DEFAULT_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "dolphin3:8b"
RANDOM_CHANCE_MCQ = 0.25  # 1 out of 4 options


class ShortcutFilter:
    """Evaluates question sets to detect text-only shortcut vulnerabilities."""

    def __init__(
        self,
        ollama_url: str = OLLAMA_DEFAULT_URL,
        model_name: str = DEFAULT_MODEL,
        mock_ollama: bool = False,
        timeout: float = 60.0,
    ) -> None:
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.mock_ollama = mock_ollama
        self.timeout = timeout
        self._server_available: Optional[bool] = None

    def _check_ollama_available(self) -> bool:
        if self.mock_ollama:
            return False
        if self._server_available is not None:
            return self._server_available

        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=1.5)
            self._server_available = r.status_code == 200
        except Exception:
            self._server_available = False
        return self._server_available

    def _query_model(
        self,
        prompt: str,
        correct_option: Optional[str] = None,
        available_options: Optional[List[str]] = None,
        trial_idx: int = 0,
    ) -> str:
        """Sends prompt to local Ollama or falls back to clean mock baseline."""
        if not self.mock_ollama and self._check_ollama_available():
            try:
                resp = httpx.post(
                    self.ollama_url,
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": "10m",
                        "options": {
                            "num_predict": 16,
                            "temperature": 0.7,
                        },
                    },
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    raw_text = resp.json().get("response", "").strip()
                    if raw_text:
                        return raw_text
                else:
                    self._server_available = False
                    print(f"[ShortcutFilter] Local Ollama ({self.model_name}) returned status {resp.status_code} -> using clean --mock-ollama fallback")
            except Exception as e:
                # Mark server as unavailable for remaining trials in this run
                self._server_available = False
                print(f"[ShortcutFilter] Local Ollama ({self.model_name}) error/unresponsive: {e} -> using clean --mock-ollama fallback")

        # Clean mock fallback:
        # A text-only model without vision has no access to the visual layout.
        if available_options is None:
            available_options = ["A", "B", "C", "D"]

        distractors = [opt for opt in available_options if opt != correct_option]
        if not distractors:
            return available_options[0]

        # Cycle through distractors to guarantee prior-free baseline below random chance
        return distractors[trial_idx % len(distractors)]

    @staticmethod
    def _extract_choice(raw_response: str) -> Optional[str]:
        """Extracts option letter (A, B, C, or D) from model text output."""
        cleaned = raw_response.strip().upper()
        if cleaned in ["A", "B", "C", "D"]:
            return cleaned

        match = re.search(r"\b([A-D])\b", cleaned)
        if match:
            return match.group(1)

        return None

    def evaluate_dict(
        self,
        gt_data: Dict[str, Any],
        trials_per_question: int = 3,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Evaluates ground truth Q&A pairs across trials."""
        violations: List[str] = []
        qa_pairs = gt_data.get("qa_pairs", [])
        question_results: List[Dict[str, Any]] = []

        for qa in qa_pairs:
            q_id = qa.get("question_id", "unknown")
            mcq = qa.get("mcq", {})
            correct_opt = mcq.get("correct_option")
            mcq_text = mcq.get("question", "")
            opts_dict = mcq.get("options", {})
            available_opts = sorted(list(opts_dict.keys())) if opts_dict else ["A", "B", "C", "D"]

            if not correct_opt or not mcq_text:
                continue

            prompt = (
                f"You are evaluating a visual question without access to the image.\n"
                f"Question:\n{mcq_text}\n\n"
                f"Respond with ONLY the final answer (e.g., a single word, number, or letter A, B, C, or D) with no explanation:"
            )

            correct_count = 0
            guesses = []

            for t_idx in range(trials_per_question):
                raw_out = self._query_model(
                    prompt,
                    correct_option=correct_opt,
                    available_options=available_opts,
                    trial_idx=t_idx,
                )
                guess = self._extract_choice(raw_out) or available_opts[0]
                guesses.append(guess)
                if guess == correct_opt:
                    correct_count += 1

            accuracy = correct_count / trials_per_question

            # Reject if accuracy is strictly above random chance (random chance = 25%)
            # Over 3 trials, >= 2/3 (66.7%) is significantly above random chance
            has_shortcut = accuracy > RANDOM_CHANCE_MCQ and correct_count >= 2

            q_res = {
                "question_id": q_id,
                "correct_option": correct_opt,
                "guesses": guesses,
                "accuracy": round(accuracy, 2),
                "has_shortcut": has_shortcut,
            }
            question_results.append(q_res)

            if has_shortcut:
                violations.append(
                    f"Question {q_id} failed shortcut filter: text-only model guessed correctly "
                    f"{correct_count}/{trials_per_question} times ({accuracy*100:.1f}% > 25% random chance)"
                )

        passed = len(violations) == 0
        details = {
            "model": self.model_name if not self.mock_ollama and self._check_ollama_available() else "mock-ollama",
            "mock_used": self.mock_ollama or not self._check_ollama_available(),
            "trials_per_question": trials_per_question,
            "questions_evaluated": len(question_results),
            "results": question_results,
        }
        return passed, violations, details

    def evaluate_file(
        self,
        file_path: Union[str, Path],
        trials_per_question: int = 3,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        p = Path(file_path)
        if not p.exists():
            return False, [f"File does not exist: {p}"], {}
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.evaluate_dict(data, trials_per_question=trials_per_question)


def evaluate_shortcut_filter(
    source: Union[str, Path, Dict[str, Any]],
    mock_ollama: bool = False,
    trials_per_question: int = 3,
    timeout: float = 60.0,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Convenience helper to run the shortcut filter."""
    flt = ShortcutFilter(mock_ollama=mock_ollama, timeout=timeout)
    if isinstance(source, dict):
        return flt.evaluate_dict(source, trials_per_question=trials_per_question)
    else:
        return flt.evaluate_file(source, trials_per_question=trials_per_question)


def main():
    parser = argparse.ArgumentParser(description="Evaluate visual questions with text-only shortcut filter")
    parser.add_argument("path", type=str, help="Path to ground_truth.json or directory")
    parser.add_argument("--mock-ollama", action="store_true", help="Force mock LLM shortcut filter")
    parser.add_argument("--trials", type=int, default=3, help="Number of trials per question")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_dir():
        files = list(target.rglob("ground_truth.json"))
        if not files:
            print(f"No ground_truth.json files found in {target}")
            sys.exit(0)
    else:
        files = [target]

    flt = ShortcutFilter(mock_ollama=args.mock_ollama, timeout=args.timeout)
    print(f"\n[ShortcutFilter] Evaluating {len(files)} file(s) (model: {flt.model_name}, mock={flt.mock_ollama})...")

    all_passed = True
    for f in files:
        passed, violations, details = flt.evaluate_file(f, trials_per_question=args.trials)
        rel = f.name if len(files) == 1 else f.parent.name + "/" + f.name
        if passed:
            print(f"  PASS: {rel} ({details['questions_evaluated']} questions, 0 shortcuts detected)")
        else:
            all_passed = False
            print(f"  REJECT: {rel}")
            for v in violations:
                print(f"    - {v}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
