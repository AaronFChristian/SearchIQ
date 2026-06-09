"""
SearchIQ — Agent 3: Profile Critic
Model: Claude Sonnet 4.6

WHY CLAUDE FOR THIS TASK:
Evaluating 10 profiles against a role brief requires nuanced judgment —
catching subtle seniority gaps, vague credential claims, and profiles that
look suspiciously polished. Claude's evaluative reasoning is best-in-class
for this kind of structured critique work. This is the human analyst
judgment layer, automated.

This is the most important agent for the SPMB interview — it demonstrates
you understand the difference between "AI generated something" and
"AI generated something a client can actually use."

Input:  role brief + list of profiles from Agent 2
Output: validated critique dict with per-profile scores + batch summary
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
from config import AGENT3_MODEL, MAX_RETRIES, RETRY_DELAY
from utils import get_logger, extract_json, RunMetadata
from schemas.schemas import validate_json_structure
from prompts.prompts import PROFILE_CRITIC_SYSTEM, PROFILE_CRITIC_USER_V2

logger = get_logger("Agent3.Critic")

CRITIQUE_REQUIRED_KEYS = ["profile_id", "confidence", "action", "issues", "strengths", "reviewer_note"]
BATCH_REQUIRED_KEYS    = ["overall_quality", "top_3_profiles", "failure_pattern"]


class ProfileCriticAgent:

    def __init__(self, api_key: str):
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install anthropic")
        logger.info(f"ProfileCriticAgent | model={AGENT3_MODEL}")

    def _call(self, role_brief: str, profiles: list) -> tuple[str, int]:
        prompt = PROFILE_CRITIC_USER_V2.format(
            role_brief=role_brief,
            profiles_json=json.dumps(profiles, indent=2)
        )
        response = self._client.messages.create(
            model=AGENT3_MODEL,
            max_tokens=8000,
            system=PROFILE_CRITIC_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        text   = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return text, tokens

    def _validate(self, data: dict) -> list[str]:
        errors = validate_json_structure(data, ["critiques", "batch_summary"], "Critique")
        if errors:
            return errors

        for c in data.get("critiques", []):
            pid = c.get("profile_id", "?")
            errors.extend(validate_json_structure(c, CRITIQUE_REQUIRED_KEYS, f"Critique#{pid}"))
            if c.get("confidence") not in ("high", "medium", "low"):
                errors.append(f"Critique#{pid}: invalid confidence '{c.get('confidence')}'")
            if c.get("action") not in ("keep", "revise", "drop"):
                errors.append(f"Critique#{pid}: invalid action '{c.get('action')}'")

        summary = data.get("batch_summary", {})
        errors.extend(validate_json_structure(summary, BATCH_REQUIRED_KEYS, "BatchSummary"))
        top3 = summary.get("top_3_profiles", [])
        if len(top3) != 3:
            errors.append(f"BatchSummary: expected 3 top profiles, got {len(top3)}")

        return errors

    def run(self, role_brief: str, profiles: list,
            metadata: RunMetadata | None = None) -> dict:
        logger.info(f"Critiquing {len(profiles)} profiles...")
        start      = time.time()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 2):
            try:
                logger.debug(f"Attempt {attempt}...")
                raw_text, tokens = self._call(role_brief, profiles)
                critique = extract_json(raw_text)

                errors = self._validate(critique)
                if errors:
                    err_str = "\n".join(f"- {e}" for e in errors)
                    logger.warning(f"Validation failed (attempt {attempt}):\n{err_str}")
                    if attempt <= MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                        continue
                    raise ValueError(f"Critique validation failed:\n{err_str}")

                duration = round(time.time() - start, 2)
                logger.info(f"Critique done | {len(critique['critiques'])} profiles reviewed | {duration}s | {tokens} tokens")
                if metadata:
                    metadata.record("Agent3.Critic", "ok", duration, tokens)
                self._save(critique, role_brief)
                return critique

            except ValueError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt} error: {e}")
                if attempt <= MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        duration = round(time.time() - start, 2)
        if metadata:
            metadata.record("Agent3.Critic", "failed", duration)
        raise RuntimeError(f"Agent3 failed. Last error: {last_error}")

    def _save(self, critique: dict, brief: str):
        Path("outputs").mkdir(exist_ok=True)
        path = Path(f"outputs/critique_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump({"brief_preview": brief[:100], "critique": critique}, f, indent=2)
        logger.debug(f"Saved -> {path}")
