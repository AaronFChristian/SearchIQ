"""
SearchIQ — Agent 1: Market Mapper
Provider: configurable — Claude (default, works now) or Gemini (upgrade)

Switch provider in config.py:
  AGENT1_PROVIDER = "claude"   # works immediately
  AGENT1_PROVIDER = "gemini"   # requires Generative Language API enabled in GCP

Input:  role brief (string)
Output: validated market map dict
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
import os
from config import AGENT1_PROVIDER, AGENT1_MODEL, MAX_RETRIES, RETRY_DELAY, DEFAULT_COMPANY_COUNT
from utils import get_logger, extract_json, RunMetadata
from schemas.schemas import validate_json_structure
from prompts.prompts import MARKET_MAPPER_SYSTEM, MARKET_MAPPER_USER_V2

logger = get_logger("Agent1.MarketMapper")


class MarketMapperAgent:

    def __init__(self, api_key: str, company_count: int = DEFAULT_COMPANY_COUNT):
        self.api_key       = api_key
        self.company_count = company_count
        self.provider      = AGENT1_PROVIDER
        self.model         = AGENT1_MODEL
        self._client       = None
        self._init_client()
        logger.info(f"MarketMapperAgent | provider={self.provider} | model={self.model} | companies={company_count}")

    def _init_client(self):
        if self.provider == "gemini":
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ImportError("Run: pip install google-genai")
        elif self.provider == "claude":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("Run: pip install anthropic")
        else:
            raise ValueError(f"Unknown provider: {self.provider}. Use 'claude' or 'gemini'.")

    def _build_prompt(self, role_brief: str) -> str:
        return MARKET_MAPPER_USER_V2.format(
            role_brief=role_brief,
            company_count=self.company_count
        )

    def _call(self, prompt: str) -> tuple[str, int]:
        """Dispatches to the configured provider. Returns (text, tokens)."""
        if self.provider == "gemini":
            return self._call_gemini(prompt)
        else:
            return self._call_claude(prompt)

    def _call_claude(self, prompt: str) -> tuple[str, int]:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=MARKET_MAPPER_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        text   = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return text, tokens

    def _call_gemini(self, prompt: str) -> tuple[str, int]:
        from google.genai import types as genai_types
        response = self._gemini_client.models.generate_content(
            model=self.model,
            contents=f"{MARKET_MAPPER_SYSTEM}\n\n---\n\n{prompt}",
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            )
        )
        text   = response.text
        tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
        return text, tokens

    def _validate(self, data: dict) -> list[str]:
        required = ["target_companies", "talent_pools", "comp_range", "search_notes"]
        errors   = validate_json_structure(data, required, "MarketMap")
        companies = data.get("target_companies", [])
        if len(companies) < 8:
            errors.append(f"Too few companies: got {len(companies)}, expected 8+")
        for i, co in enumerate(companies[:3]):
            if "tier" not in co:
                errors.append(f"Company #{i+1} missing 'tier'")
            if "suggested_titles" not in co:
                errors.append(f"Company #{i+1} missing 'suggested_titles'")
        if len(data.get("talent_pools", [])) != 3:
            errors.append(f"Expected 3 talent_pools, got {len(data.get('talent_pools', []))}")
        return errors

    def run(self, role_brief: str, metadata: RunMetadata | None = None) -> dict:
        logger.info(f"Starting market mapping via {self.provider}...")
        start  = time.time()
        prompt = self._build_prompt(role_brief)

        last_error = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                logger.debug(f"Attempt {attempt}...")
                raw_text, tokens = self._call(prompt)
                market_map = extract_json(raw_text)

                errors = self._validate(market_map)
                if errors:
                    err_str = "\n".join(f"- {e}" for e in errors)
                    logger.warning(f"Validation failed (attempt {attempt}):\n{err_str}")
                    if attempt <= MAX_RETRIES:
                        prompt += f"\n\nPrevious attempt had these issues — fix them:\n{err_str}"
                        time.sleep(RETRY_DELAY)
                        continue
                    raise ValueError(f"Market map failed validation:\n{err_str}")

                duration = round(time.time() - start, 2)
                logger.info(f"Market map done | {len(market_map['target_companies'])} companies | {duration}s | {tokens} tokens")
                if metadata:
                    metadata.record("Agent1.MarketMapper", "ok", duration, tokens)
                self._save(market_map, role_brief)
                return market_map

            except ValueError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt} error: {e}")
                if attempt <= MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        duration = round(time.time() - start, 2)
        if metadata:
            metadata.record("Agent1.MarketMapper", "failed", duration)
        raise RuntimeError(f"Agent1 failed. Last error: {last_error}")

    def _save(self, data: dict, brief: str):
        Path("outputs").mkdir(exist_ok=True)
        path = Path(f"outputs/market_map_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump({"brief_preview": brief[:100], "market_map": data}, f, indent=2)
        logger.debug(f"Saved -> {path}")
