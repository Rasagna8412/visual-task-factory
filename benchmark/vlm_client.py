"""VLM Client module for Visual Task Factory (Milestone 3).

Supports:
  - OpenAI-compatible vision endpoints (OpenAI, OpenRouter, Custom gateways)
  - Google Gemini API (generateContent with inline base64 image)
  - Anthropic Messages API
  - Local Ollama vision endpoint
  - Mock VLM mode with 2 realistic frontier profiles (mock-frontier-strong, mock-frontier-mid)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx


@dataclass
class VLMResponse:
    raw_text: str
    model: str
    provider: str
    latency_ms: float
    metadata: Dict[str, Any]


def encode_image_to_base64(image_path: Union[str, Path]) -> str:
    """Reads image file and returns base64-encoded string."""
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class VLMClient:
    """Multi-provider asynchronous VLM client with mock simulation."""

    def __init__(
        self,
        provider: str = "mock",
        model: str = "mock-frontier-strong",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.getenv("VLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.base_url = base_url
        self.timeout = timeout

    async def query(
        self,
        prompt: str,
        image_path: Optional[Union[str, Path]] = None,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> VLMResponse:
        """Queries the configured VLM provider with a prompt and an image."""
        t0 = asyncio.get_event_loop().time()

        if self.provider == "mock" or self.model.startswith("mock-"):
            raw_text, meta = self._simulate_mock_response(prompt, task_context)
            dt = (asyncio.get_event_loop().time() - t0) * 1000.0
            return VLMResponse(
                raw_text=raw_text,
                model=self.model,
                provider="mock",
                latency_ms=round(dt, 1),
                metadata=meta,
            )

        b64_image = encode_image_to_base64(image_path) if image_path else ""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if self.provider in ["openai", "openrouter", "gateway"]:
                raw_text, meta = await self._query_openai_compatible(client, prompt, b64_image)
            elif self.provider in ["gemini", "google"]:
                raw_text, meta = await self._query_gemini(client, prompt, b64_image)
            elif self.provider in ["anthropic", "claude"]:
                raw_text, meta = await self._query_anthropic(client, prompt, b64_image)
            elif self.provider in ["ollama", "local"]:
                raw_text, meta = await self._query_ollama(client, prompt, b64_image)
            else:
                raise ValueError(f"Unknown VLM provider: '{self.provider}'")

        dt = (asyncio.get_event_loop().time() - t0) * 1000.0
        return VLMResponse(
            raw_text=raw_text,
            model=self.model,
            provider=self.provider,
            latency_ms=round(dt, 1),
            metadata=meta,
        )

    def query_sync(
        self,
        prompt: str,
        image_path: Optional[Union[str, Path]] = None,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> VLMResponse:
        """Synchronous wrapper around query()."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.query(prompt, image_path, task_context))

    async def _query_openai_compatible(
        self, client: httpx.AsyncClient, prompt: str, b64_image: str
    ) -> Tuple[str, Dict[str, Any]]:
        url = (self.base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        content = [{"type": "text", "text": prompt}]
        if b64_image:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_image}"},
            })

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.0,
            "max_tokens": 128,
        }
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text, {"usage": data.get("usage", {})}

    async def _query_gemini(
        self, client: httpx.AsyncClient, prompt: str, b64_image: str
    ) -> Tuple[str, Dict[str, Any]]:
        api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        )
        parts = [{"text": prompt}]
        if b64_image:
            parts.append({"inline_data": {"mime_type": "image/png", "data": b64_image}})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 128},
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text, {}

    async def _query_anthropic(
        self, client: httpx.AsyncClient, prompt: str, b64_image: str
    ) -> Tuple[str, Dict[str, Any]]:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        content = []
        if b64_image:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64_image},
            })
        content.append({"type": "text", "text": prompt})

        payload = {
            "model": self.model,
            "max_tokens": 128,
            "messages": [{"role": "user", "content": content}],
        }
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"].strip()
        return text, {}

    async def _query_ollama(
        self, client: httpx.AsyncClient, prompt: str, b64_image: str
    ) -> Tuple[str, Dict[str, Any]]:
        url = (self.base_url or "http://localhost:11434").rstrip("/") + "/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [b64_image] if b64_image else [],
            "stream": False,
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        return text, {}

    def _simulate_mock_response(
        self, prompt: str, task_context: Optional[Dict[str, Any]]
    ) -> Tuple[str, Dict[str, Any]]:
        """Simulates realistic VLM responses for mock-frontier-strong and mock-frontier-mid.

        Models:
          - Degradation as difficulty (easy -> med -> hard) and Shapely occlusion increase.
          - MCQ shortcut advantage (higher accuracy on MCQ than open_ended).
          - Realistic abstention and hallucination rates.
          - Deterministic outputs based on task hash.
        """
        if not task_context:
            return "cannot_determine", {"simulated": True}

        format_mode = task_context.get("format", "open_ended")
        correct_answer = str(task_context.get("correct_answer", "0"))
        correct_option = str(task_context.get("correct_option", "A"))
        mcq_options = task_context.get("mcq_options", {"A": "0", "B": "1", "C": "2", "D": "3"})
        difficulty = task_context.get("difficulty", "medium")
        mean_occlusion = float(task_context.get("mean_occlusion", 0.35))
        is_unanswerable = task_context.get("is_unanswerable", False)
        is_counterfactual = task_context.get("is_counterfactual", False)
        sample_seed = int(task_context.get("seed", 42))
        q_id = task_context.get("question_id", "q1")

        # Deterministic PRNG seeded by task characteristics
        h_str = f"{self.model}_{sample_seed}_{q_id}_{format_mode}_{difficulty}"
        h_val = int(hashlib.sha256(h_str.encode()).hexdigest(), 16) % 1000000
        prng = random.Random(h_val)

        # Baseline parameters per model profile
        if self.model == "mock-frontier-strong":
            base_acc = 0.90
            diff_penalties = {"easy": 0.0, "medium": 0.08, "hard": 0.18}
            occlusion_slope = 0.22
            mcq_boost = 0.08
            abstention_acc = 0.85  # 85% correct abstention, 15% hallucination
        else:  # mock-frontier-mid
            base_acc = 0.74
            diff_penalties = {"easy": 0.0, "medium": 0.15, "hard": 0.32}
            occlusion_slope = 0.35
            mcq_boost = 0.18  # larger MCQ shortcut gap
            abstention_acc = 0.52  # 52% correct abstention, 48% hallucination

        # Compute accuracy probability
        if is_unanswerable:
            prob_success = abstention_acc
            # MCQ guessing boost on abstention options
            if format_mode == "mcq":
                prob_success = min(0.95, prob_success + mcq_boost * 0.5)
        else:
            diff_penalty = diff_penalties.get(difficulty, 0.10)
            prob_success = base_acc - diff_penalty - (occlusion_slope * mean_occlusion)
            if format_mode == "mcq":
                prob_success += mcq_boost
            prob_success = max(0.20, min(0.98, prob_success))

        # Roll against probability
        roll = prng.uniform(0.0, 1.0)
        is_correct = roll <= prob_success

        if format_mode == "mcq":
            if is_correct:
                ans = correct_option
            else:
                distractor_opts = [k for k in mcq_options.keys() if k != correct_option]
                ans = prng.choice(distractor_opts) if distractor_opts else "B"
        else:
            # open_ended
            if is_correct:
                ans = correct_answer
            else:
                if is_unanswerable:
                    # Hallucination: claims to see a shape instead of cannot_determine
                    hallucinations = ["red circle", "blue square", "green triangle", "purple square"]
                    ans = prng.choice(hallucinations)
                elif correct_answer in ["yes", "no"]:
                    ans = "no" if correct_answer == "yes" else "yes"
                elif correct_answer.isdigit():
                    num = int(correct_answer)
                    offset = prng.choice([-2, -1, 1, 2, 3])
                    ans = str(max(0, num + offset))
                else:
                    ans = "cannot_determine"

        meta = {
            "simulated": True,
            "model_profile": self.model,
            "prob_success": round(prob_success, 3),
            "roll": round(roll, 3),
            "simulated_correct": is_correct,
        }
        return ans, meta


def get_vlm_client(
    model: str = "mock-frontier-strong",
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    config_path: str = "config/models.json",
) -> VLMClient:
    """Helper factory for VLM clients with config/models.json lookup."""
    models_cfg = {}
    p = Path(config_path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                models_cfg = json.load(f)
        except Exception:
            pass

    if model in models_cfg:
        cfg = models_cfg[model]
        provider = provider or cfg.get("provider", "mock")
        if not api_key and "env_key" in cfg:
            api_key = os.getenv(cfg["env_key"], "")
        if not base_url:
            if "base_url_env" in cfg:
                base_url = os.getenv(cfg["base_url_env"], cfg.get("base_url"))
            else:
                base_url = cfg.get("base_url")

    if provider is None:
        if model.startswith("mock-"):
            provider = "mock"
        elif "gpt" in model or "openai" in model:
            provider = "openai"
        elif "gemini" in model:
            provider = "gemini"
        elif "claude" in model:
            provider = "anthropic"
        elif "ollama" in model or "llava" in model:
            provider = "ollama"
        else:
            provider = "mock"

    return VLMClient(provider=provider, model=model, api_key=api_key, base_url=base_url)
