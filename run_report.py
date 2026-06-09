"""
SearchIQ — Agent 5 standalone runner.
Loads the full pipeline output and generates an HTML executive search brief.

Usage:
    python run_report.py                              # loads outputs/day2_full_pipeline.json
    python run_report.py --input path/to/output.json
    python run_report.py --open                       # auto-opens in browser after generation

The HTML report is saved to outputs/reports/searchiq_brief_<timestamp>.html.
Print to PDF via browser (Cmd+P / Ctrl+P) to produce a client-ready PDF.
"""

import os
import sys
import json
import argparse
import webbrowser
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.agent5_report_generator import ReportGeneratorAgent
from utils import RunMetadata, get_logger

logger = get_logger("ReportRunner")


def get_anthropic_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("\n  ✗  Missing ANTHROPIC_API_KEY in .env\n")
        sys.exit(1)
    return key


def main():
    parser = argparse.ArgumentParser(description="SearchIQ — Generate HTML search brief (Agent 5)")
    parser.add_argument(
        "--input", default="outputs/day2_full_pipeline.json",
        help="Path to full pipeline JSON (default: outputs/day2_full_pipeline.json)"
    )
    parser.add_argument(
        "--open", action="store_true",
        help="Open the generated report in the default browser"
    )
    args = parser.parse_args()

    # Load pipeline output
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"\n  ✗  Pipeline output not found: {input_path}")
        print("     Run python run_day2.py first\n")
        sys.exit(1)

    logger.info(f"Loading pipeline output from {input_path}")
    with open(input_path, encoding="utf-8") as f:
        pipeline_data = json.load(f)

    n_profiles = len(pipeline_data.get("profiles", []))
    quality    = pipeline_data.get("critique", {}).get("batch_summary", {}).get("overall_quality", "unknown")
    logger.info(f"Loaded: {n_profiles} profiles | slate quality: {quality}")

    # Run Agent 5
    api_key  = get_anthropic_key()
    metadata = RunMetadata(pipeline_data.get("role_brief", ""))

    agent = ReportGeneratorAgent(api_key=api_key)
    result = agent.run(pipeline_data, metadata=metadata)

    # Summary
    print(metadata.summary())
    print(f"  ✓  Search brief generated")
    print(f"  ✓  Engagement:  {result['engagement']}")
    print(f"  ✓  Output:      {result['html_path']}")
    print(f"  ✓  Tokens used: {result['tokens']:,}")
    print(f"\n     → Open in browser and print to PDF for client delivery\n")

    if args.open:
        path_uri = Path(result["html_path"]).resolve().as_uri()
        webbrowser.open(path_uri)
        print(f"  ✓  Opened in browser: {path_uri}\n")


if __name__ == "__main__":
    main()
