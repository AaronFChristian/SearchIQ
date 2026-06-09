"""
SearchIQ — shared utilities used by all agents.

Centralising these means:
  - Every agent handles JSON extraction the same way
  - Retry logic is consistent
  - Logs are structured and comparable across agents
"""

import json
import time
import logging
import re
from datetime import datetime
from pathlib import Path

# --- Logger setup ---
def get_logger(name: str) -> logging.Logger:
    """Returns a named logger that writes to console + logs/run.log."""
    Path("logs").mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s  %(name)-18s  %(levelname)-7s  %(message)s",
                            datefmt="%H:%M:%S")
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    # File handler
    fh = logging.FileHandler("logs/run.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# --- JSON extraction ---
def extract_json(text: str) -> dict | list:
    """
    Robustly extracts JSON from an LLM response.

    LLMs often wrap JSON in markdown fences (```json ... ```) or add
    preamble text before the JSON starts. This handles all common cases:
      1. Clean JSON string
      2. JSON inside ```json ... ``` fences
      3. JSON after preamble text (finds first { or [)
    
    Raises ValueError if no valid JSON found.
    """
    # Strip markdown fences
    text = text.strip()
    fenced = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if fenced:
        text = fenced.group(1).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first JSON object or array
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Walk backwards from end to find the matching close
        end = text.rfind(end_char)
        if end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No valid JSON found in LLM response. Preview: {text[:200]}")


# --- Retry wrapper ---
def with_retry(fn, max_retries: int = 2, delay: float = 1.5, logger=None):
    """
    Calls fn(), retrying up to max_retries times if it raises an exception.
    Logs each attempt. Returns the result of fn() on success.

    Usage:
        result = with_retry(lambda: agent.run(brief), max_retries=2)
    """
    log = logger or get_logger("retry")
    last_error = None
    for attempt in range(1, max_retries + 2):  # +2: initial + retries
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt <= max_retries:
                log.warning(f"Attempt {attempt} failed: {e}. Retrying in {delay}s…")
                time.sleep(delay)
            else:
                log.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
    raise last_error


# --- Run metadata ---
class RunMetadata:
    """
    Tracks a single pipeline run: timing, token usage, agent outcomes.
    Printed as a clean summary at the end of each run.
    """
    def __init__(self, brief: str):
        self.brief_preview  = brief[:80] + "..." if len(brief) > 80 else brief
        self.started_at     = datetime.now()
        self.agents         = {}   # agent_name → {status, duration_s, tokens}

    def record(self, agent_name: str, status: str, duration_s: float, tokens: int = 0):
        self.agents[agent_name] = {
            "status":     status,
            "duration_s": round(duration_s, 2),
            "tokens":     tokens
        }

    def summary(self) -> str:
        total_s      = round((datetime.now() - self.started_at).total_seconds(), 1)
        total_tokens = sum(a["tokens"] for a in self.agents.values())
        lines = [
            "",
            "━" * 56,
            "  SearchIQ run summary",
            f"  Brief: {self.brief_preview}",
            f"  Started: {self.started_at.strftime('%H:%M:%S')}   Total time: {total_s}s",
            "─" * 56,
        ]
        for name, data in self.agents.items():
            status_icon = "✓" if data["status"] == "ok" else "✗"
            tok_str     = f"{data['tokens']:,} tokens" if data["tokens"] else "n/a"
            lines.append(f"  {status_icon}  {name:<22} {data['duration_s']:>5}s   {tok_str}")
        lines += [
            "─" * 56,
            f"  Total tokens: {total_tokens:,}",
            "━" * 56,
            "",
        ]
        return "\n".join(lines)
