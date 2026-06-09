"""
SearchIQ — Day 1 test runner
Runs Agent 1 (Market Mapper) → Agent 2 (Profile Generator) end-to-end.

Usage:  python run_day1.py
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.agent1_market_mapper     import MarketMapperAgent
from agents.agent2_profile_generator import ProfileGeneratorAgent
from utils import RunMetadata, get_logger
from config import AGENT1_PROVIDER, AGENT2_PROVIDER

logger = get_logger("Day1Runner")

ROLE_BRIEF = """
We are conducting an executive search for a Chief Financial Officer (CFO)
at a Series C fintech company headquartered in San Francisco. The company
provides embedded lending infrastructure for SMBs and has reached $120M ARR
with 200 employees. They are preparing for a Series D raise of $150-200M
within 18 months and targeting a path to IPO within 3-4 years.

Ideal candidate profile:
- 15+ years in finance with 5+ years in a CFO or VP Finance role
- Deep experience with capital markets: equity raises, debt facilities,
  or IPO preparation
- Background in fintech, payments, lending, or marketplace businesses strongly preferred
- Proven ability to build and scale a finance function from ~$100M to $500M+ ARR
- Strong FP&A foundation; able to partner closely with the CEO on strategy
- Experience with investor relations and board communication

This is a high-visibility, highly strategic role reporting directly to the CEO.
The company's board includes partners from Andreessen Horowitz and Sequoia.
"""


def get_api_key(provider: str) -> str:
    """Returns the correct API key for the given provider."""
    key_map = {
        "claude":  "ANTHROPIC_API_KEY",
        "gemini":  "GEMINI_API_KEY",
        "openai":  "OPENAI_API_KEY",
    }
    env_var = key_map.get(provider)
    if not env_var:
        raise ValueError(f"Unknown provider: {provider}")
    key = os.getenv(env_var, "").strip()
    if not key:
        print(f"\n  x  Missing {env_var} in .env (required for provider '{provider}')")
        print(f"     Run: python check_keys.py  for diagnosis\n")
        sys.exit(1)
    return key


def pretty_print_market_map(mm: dict):
    print("\n" + "=" * 60)
    print(f"  MARKET MAP  (Agent 1 / {AGENT1_PROVIDER})")
    print("=" * 60)
    print(f"\n  Comp range:   {mm.get('comp_range', 'n/a')}")
    print(f"  Search notes: {mm.get('search_notes', '')}\n")

    for tier in ["primary", "secondary", "stretch"]:
        cos = [c for c in mm["target_companies"] if c.get("tier") == tier]
        if cos:
            print(f"  [{tier.upper()}]")
            for co in cos:
                titles = ", ".join(co.get("suggested_titles", []))
                print(f"    * {co['name']}")
                print(f"      {co.get('rationale', '')}")
                print(f"      Titles to search: {titles}")
            print()

    print("  TALENT POOLS")
    for pool in mm.get("talent_pools", []):
        print(f"    [{pool['cluster_name']}]")
        print(f"     {pool['description']}")
        print(f"     Why relevant: {pool['why_relevant']}")
        print()


def pretty_print_profiles(profiles: list):
    print("\n" + "=" * 60)
    print(f"  PROFILES  (Agent 2 / {AGENT2_PROVIDER})  —  {len(profiles)} generated")
    print("=" * 60)
    for p in profiles:
        summary = p.get("career_summary", "")
        why     = p.get("why_they_fit", "")
        creds   = p.get("key_credentials", [])
        probes  = p.get("questions_to_probe", [])
        print(f"\n  [{p['profile_id']}] {p['name']}")
        print(f"       {p['current_title']} @ {p['current_company']}")
        print(f"       {summary[:130]}..." if len(summary) > 130 else f"       {summary}")
        print(f"       WHY FIT:    {why[:110]}..." if len(why) > 110 else f"       WHY FIT:    {why}")
        print(f"       CREDENTIAL: {creds[0] if creds else 'n/a'}")
        print(f"       PROBE:      {probes[0] if probes else 'n/a'}")
    print()


def main():
    metadata = RunMetadata(ROLE_BRIEF)
    logger.info(f"SearchIQ Day 1 — Agent1={AGENT1_PROVIDER} | Agent2={AGENT2_PROVIDER}")

    # Agent 1: Market Mapper
    logger.info(f"Running Agent 1 ({AGENT1_PROVIDER})...")
    mapper     = MarketMapperAgent(api_key=get_api_key(AGENT1_PROVIDER))
    market_map = mapper.run(ROLE_BRIEF, metadata=metadata)
    pretty_print_market_map(market_map)

    # Agent 2: Profile Generator
    logger.info(f"Running Agent 2 ({AGENT2_PROVIDER})...")
    generator = ProfileGeneratorAgent(api_key=get_api_key(AGENT2_PROVIDER))
    profiles  = generator.run(ROLE_BRIEF, market_map, metadata=metadata)
    pretty_print_profiles(profiles)

    # Summary
    print(metadata.summary())

    # Save combined output for Day 2
    out = Path("outputs/day1_combined.json")
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        json.dump({"role_brief": ROLE_BRIEF, "market_map": market_map, "profiles": profiles}, f, indent=2)
    logger.info(f"Day 2 input saved -> {out}")
    print(f"  Day 2 input ready: {out}\n")


if __name__ == "__main__":
    main()
