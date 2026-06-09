"""
SearchIQ — Day 2 runner
Loads Day 1 output → runs Agent 3 (Critic) → Agent 4 (Exporter)

Usage:
    python run_day2.py                          # uses outputs/day1_combined.json
    python run_day2.py --input path/to/file.json

Google Sheets export (optional):
    Set in .env:
        GOOGLE_SHEETS_CREDS_PATH=/path/to/service_account.json
        GOOGLE_SHEET_ID=your_sheet_id
    Without these, output writes to CSV in outputs/
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.agent3_profile_critic import ProfileCriticAgent
from agents.agent4_exporter       import SheetsExporter
from utils import RunMetadata, get_logger

logger = get_logger("Day2Runner")


def get_anthropic_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("\n  x  Missing ANTHROPIC_API_KEY in .env\n")
        sys.exit(1)
    return key


def pretty_print_critique(critique: dict, profiles: list):
    pid_to_name = {p["profile_id"]: p["name"] for p in profiles}

    print("\n" + "=" * 60)
    print("  CRITIQUE  (Agent 3 / Claude Sonnet)")
    print("=" * 60)

    conf_icon = {"high": "HI", "medium": "MD", "low": "LO"}
    act_icon  = {"keep": "KEEP  ", "revise": "REVISE", "drop": "DROP  "}

    for c in sorted(critique["critiques"], key=lambda x: x["profile_id"]):
        pid  = c["profile_id"]
        name = pid_to_name.get(pid, f"Profile {pid}")
        conf = c.get("confidence", "?")
        act  = c.get("action", "?")

        print(f"\n  [{pid:02d}] {name}")
        print(f"       [{conf_icon.get(conf,'??')}] [{act_icon.get(act,'?')}]  {c.get('reviewer_note','')}")

        issues = c.get("issues", [])
        if issues:
            print(f"       ISSUES:")
            for issue in issues:
                print(f"         - {issue[:100]}{'...' if len(issue)>100 else ''}")

        strengths = c.get("strengths", [])
        if strengths:
            print(f"       STRENGTHS:")
            for s in strengths:
                print(f"         + {s[:100]}{'...' if len(s)>100 else ''}")

    summary = critique.get("batch_summary", {})
    print("\n" + "=" * 60)
    print("  BATCH SUMMARY")
    print("=" * 60)
    qual   = summary.get("overall_quality", "?").upper()
    top3   = summary.get("top_3_profiles", [])
    top3_names = [f"#{pid} {pid_to_name.get(pid,'')}" for pid in top3]
    print(f"\n  Overall quality:  {qual}")
    print(f"  Top 3 to present: {', '.join(top3_names)}")
    print(f"  Failure pattern:  {summary.get('failure_pattern','')}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="outputs/day1_combined.json",
                        help="Path to Day 1 combined JSON output")
    args = parser.parse_args()

    # Load Day 1 output
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"\n  x  Day 1 output not found: {input_path}")
        print("     Run python run_day1.py first\n")
        sys.exit(1)

    logger.info(f"Loading Day 1 output from {input_path}")
    with open(input_path) as f:
        day1 = json.load(f)

    role_brief = day1["role_brief"]
    profiles   = day1["profiles"]
    market_map = day1["market_map"]

    logger.info(f"Loaded {len(profiles)} profiles")

    metadata   = RunMetadata(role_brief)
    anthropic_key = get_anthropic_key()

    # Agent 3: Profile Critic
    logger.info("Running Agent 3 (Profile Critic / Claude Sonnet)...")
    critic   = ProfileCriticAgent(api_key=anthropic_key)
    critique = critic.run(role_brief, profiles, metadata=metadata)
    pretty_print_critique(critique, profiles)

    # Agent 4: Exporter
    logger.info("Running Agent 4 (Exporter)...")
    exporter = SheetsExporter()
    result   = exporter.run(profiles, critique, metadata=metadata)

    # Summary
    print(metadata.summary())

    dest = result["destination"]
    if dest == "sheets":
        print(f"  Google Sheet written:  {result['url_or_path']}")
    else:
        print(f"  CSV written:           {result['url_or_path']}")

    print(f"  Total profiles:        {result['total_rows']}")
    print(f"  Flagged for review:    {result['flagged_rows']}")

    # Save full pipeline output
    full_output = Path("outputs/day2_full_pipeline.json")
    with open(full_output, "w") as f:
        json.dump({
            "role_brief":  role_brief,
            "market_map":  market_map,
            "profiles":    profiles,
            "critique":    critique,
            "export":      result,
        }, f, indent=2)
    logger.info(f"Full pipeline output saved -> {full_output}")
    print(f"  Full pipeline JSON:    {full_output}\n")


if __name__ == "__main__":
    main()
