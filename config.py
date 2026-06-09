"""
SearchIQ — configuration and constants.

MODEL STRATEGY (interview-explainable):

  CURRENT (working now — all Claude):
    claude-haiku-4-5    → Agent 1: market mapping (fast, cheap)
    claude-sonnet-4-6   → Agent 2: profile generation (stronger output quality)
    claude-sonnet-4-6   → Agent 3: evaluative critique (Day 2)

  UPGRADE PATH (once Gemini API enabled + OpenAI billing added):
    Gemini 2.0 Flash → Agent 1: set AGENT1_PROVIDER = "gemini"
    GPT-4o-mini      → Agent 2: set AGENT2_PROVIDER = "openai"
"""

# Agent 1 — Market Mapper
AGENT1_PROVIDER = "claude"
AGENT1_MODEL    = "claude-haiku-4-5"        # fast + cheap for research synthesis

# Agent 2 — Profile Generator
AGENT2_PROVIDER = "claude"
AGENT2_MODEL    = "claude-sonnet-4-6"       # stronger instruction-following for 10-profile schema

# Agent 3 — Profile Critic (Day 2)
AGENT3_PROVIDER = "claude"
AGENT3_MODEL    = "claude-sonnet-4-6"       # best evaluative reasoning

# Legacy aliases (keeps existing agent import lines working)
GEMINI_MODEL  = "gemini-2.0-flash"
OPENAI_MODEL  = "gpt-4o-mini"
CLAUDE_MODEL  = AGENT3_MODEL

# Pipeline settings
SCHEMA_VERSION        = "1.0"
MAX_RETRIES           = 2
RETRY_DELAY           = 1.5
DEFAULT_NUM_PROFILES  = 10
DEFAULT_COMPANY_COUNT = 12
