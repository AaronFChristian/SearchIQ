"""
SearchIQ — Agent 2: Profile Generator
Provider: configurable — Claude (default, works now) or OpenAI (upgrade)

Switch provider in config.py:
  AGENT2_PROVIDER = "claude"   # works immediately
  AGENT2_PROVIDER = "openai"   # requires OpenAI billing credits

Input:  role brief + market map dict from Agent 1
Output: list of 10 validated profile dicts
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
import os
from config import AGENT2_PROVIDER, AGENT2_MODEL, MAX_RETRIES, RETRY_DELAY, DEFAULT_NUM_PROFILES
from utils import get_logger, extract_json, RunMetadata
from schemas.schemas import validate_json_structure
from prompts.prompts import PROFILE_GENERATOR_SYSTEM, PROFILE_GENERATOR_USER_V2

logger = get_logger("Agent2.ProfileGen")

PROFILE_REQUIRED_KEYS = [
    "profile_id", "name", "current_title", "current_company",
    "career_summary", "key_credentials", "why_they_fit", "questions_to_probe"
]


class ProfileGeneratorAgent:

    def __init__(self, api_key: str, num_profiles: int = DEFAULT_NUM_PROFILES):
        self.api_key      = api_key
        self.num_profiles = num_profiles
        self.provider     = AGENT2_PROVIDER
        self.model        = AGENT2_MODEL
        self._client      = None
        self._init_client()
        logger.info(f"ProfileGeneratorAgent | provider={self.provider} | model={self.model} | profiles={num_profiles}")

    def _init_client(self):
        if self.provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("Run: pip install openai")
        elif self.provider == "claude":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("Run: pip install anthropic")
        else:
            raise ValueError(f"Unknown provider: {self.provider}. Use 'claude' or 'openai'.")

    def _build_content(self, role_brief: str, market_map: dict, corrective_note: str = "") -> str:
        user_content = PROFILE_GENERATOR_USER_V2.format(
            role_brief=role_brief,
            market_map_json=json.dumps(market_map, indent=2),
            num_profiles=self.num_profiles
        )
        if corrective_note:
            user_content += f"\n\nPREVIOUS ATTEMPT ISSUES — fix these:\n{corrective_note}"
        return user_content

    def _call(self, role_brief: str, market_map: dict, corrective_note: str = "") -> tuple[str, int]:
        if self.provider == "openai":
            return self._call_openai(role_brief, market_map, corrective_note)
        else:
            return self._call_claude(role_brief, market_map, corrective_note)

    def _call_claude(self, role_brief: str, market_map: dict, corrective_note: str = "") -> tuple[str, int]:
        system  = PROFILE_GENERATOR_SYSTEM.format(num_profiles=self.num_profiles)
        content = self._build_content(role_brief, market_map, corrective_note)
        response = self._client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": content}]
        )
        text   = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return text, tokens

    def _call_openai(self, role_brief: str, market_map: dict, corrective_note: str = "") -> tuple[str, int]:
        system  = PROFILE_GENERATOR_SYSTEM.format(num_profiles=self.num_profiles)
        content = self._build_content(role_brief, market_map, corrective_note)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": content}
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=6000,
        )
        text   = response.choices[0].message.content
        tokens = response.usage.total_tokens
        return text, tokens

    def _unwrap(self, data) -> list:
        """Handle both bare arrays and wrapped objects from LLM responses."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["profiles", "candidates", "executives", "results", "data"]:
                if key in data and isinstance(data[key], list):
                    logger.debug(f"Unwrapped from key: '{key}'")
                    return data[key]
            if all(str(k).isdigit() for k in data.keys()):
                return list(data.values())
        raise ValueError(f"Cannot extract profile list from: {type(data)}")

    def _validate(self, profiles: list) -> list[str]:
        errors = []
        if not isinstance(profiles, list):
            return ["Expected a JSON array at top level"]
        if len(profiles) != self.num_profiles:
            errors.append(f"Expected {self.num_profiles} profiles, got {len(profiles)}")
        for i, p in enumerate(profiles):
            name = p.get("name", f"Profile #{i+1}")
            errors.extend(validate_json_structure(p, PROFILE_REQUIRED_KEYS, name))
            if len(p.get("why_they_fit", "")) < 40:
                errors.append(f"[{name}] why_they_fit too short/generic")
            if len(p.get("key_credentials", [])) < 3:
                errors.append(f"[{name}] fewer than 3 key_credentials")
            if len(p.get("questions_to_probe", [])) < 2:
                errors.append(f"[{name}] fewer than 2 questions_to_probe")
        return errors

    def run(self, role_brief: str, market_map: dict, metadata: RunMetadata | None = None) -> list[dict]:
        logger.info(f"Generating {self.num_profiles} profiles via {self.provider}...")
        start           = time.time()
        corrective_note = ""
        last_error      = None

        for attempt in range(1, MAX_RETRIES + 2):
            try:
                logger.debug(f"Attempt {attempt}...")
                raw_text, tokens = self._call(role_brief, market_map, corrective_note)
                data     = extract_json(raw_text)
                profiles = self._unwrap(data)

                errors = self._validate(profiles)
                if errors:
                    err_str = "\n".join(f"- {e}" for e in errors)
                    logger.warning(f"Validation failed (attempt {attempt}):\n{err_str}")
                    if attempt <= MAX_RETRIES:
                        corrective_note = err_str
                        time.sleep(RETRY_DELAY)
                        continue
                    raise ValueError(f"Profile generation failed validation:\n{err_str}")

                duration = round(time.time() - start, 2)
                logger.info(f"Profiles done | {len(profiles)} profiles | {duration}s | {tokens} tokens")
                if metadata:
                    metadata.record("Agent2.ProfileGen", "ok", duration, tokens)
                self._save(profiles, role_brief)
                return profiles

            except ValueError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt} error: {e}")
                if attempt <= MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        duration = round(time.time() - start, 2)
        if metadata:
            metadata.record("Agent2.ProfileGen", "failed", duration)
        raise RuntimeError(f"Agent2 failed. Last error: {last_error}")

    def _save(self, profiles: list, brief: str):
        Path("outputs").mkdir(exist_ok=True)
        path = Path(f"outputs/profiles_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump({"brief_preview": brief[:100], "profiles": profiles}, f, indent=2)
        logger.debug(f"Saved -> {path}")
