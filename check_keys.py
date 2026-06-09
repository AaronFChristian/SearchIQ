"""
SearchIQ — standalone API key checker.
Run this before run_day1.py.

Usage:  python check_keys.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from config import AGENT1_PROVIDER, AGENT1_MODEL, AGENT2_PROVIDER, AGENT2_MODEL

def check_claude(label: str, model: str):
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print(f"  [{label}]  x  ANTHROPIC_API_KEY missing from .env")
        return False
    print(f"  [{label}]  Key loaded: {key[:8]}...{key[-4:]}")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply with just the word: WORKING"}]
        )
        print(f"  [{label}]  ok  Valid | model={model} | response={resp.content[0].text.strip()!r}")
        return True
    except Exception as e:
        print(f"  [{label}]  x  FAILED: {str(e)[:120]}")
        return False

def check_gemini():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("  [GEMINI]  -  Key missing (optional upgrade)")
        return None
    print(f"  [GEMINI]  Key loaded: {key[:8]}...{key[-4:]}")
    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Reply with just the word: WORKING",
            config=genai_types.GenerateContentConfig(max_output_tokens=10)
        )
        print(f"  [GEMINI]  ok  Valid | response={resp.text.strip()!r}")
        print("  [GEMINI]  To use: set AGENT1_PROVIDER='gemini' in config.py")
        return True
    except Exception as e:
        err = str(e)
        print(f"  [GEMINI]  x  FAILED: {err[:120]}")
        if "API_KEY_INVALID" in err or "API key not valid" in err:
            print("  [GEMINI]  Fix: console.cloud.google.com -> select your project")
            print("            -> APIs & Services -> Enable 'Generative Language API'")
            print("            -> Wait 60s, re-run this check")
        return False

def check_openai():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        print("  [OPENAI]  -  Key missing (optional upgrade)")
        return None
    print(f"  [OPENAI]  Key loaded: {key[:8]}...{key[-4:]}")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Reply with just the word: WORKING"}],
            max_tokens=10
        )
        print(f"  [OPENAI]  ok  Valid | response={resp.choices[0].message.content.strip()!r}")
        print("  [OPENAI]  To use: set AGENT2_PROVIDER='openai' in config.py")
        return True
    except Exception as e:
        err = str(e)
        print(f"  [OPENAI]  x  FAILED: {err[:120]}")
        if "insufficient_quota" in err or "429" in err:
            print("  [OPENAI]  Fix: platform.openai.com/settings/billing -> add $5 credits")
        return False

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  SearchIQ — API key check")
    print(f"  Agent1: {AGENT1_PROVIDER}/{AGENT1_MODEL}")
    print(f"  Agent2: {AGENT2_PROVIDER}/{AGENT2_MODEL}")
    print("="*55 + "\n")

    print("  --- REQUIRED (pipeline runs on these) ---\n")
    c1 = check_claude("AGENT1/Claude", AGENT1_MODEL)
    print()
    c2 = check_claude("AGENT2/Claude", AGENT2_MODEL)
    print()

    print("  --- OPTIONAL UPGRADES ---\n")
    check_gemini()
    print()
    check_openai()
    print()

    if c1 and c2:
        print("  All required keys OK — run: python run_day1.py\n")
    else:
        print("  Fix ANTHROPIC_API_KEY in .env, then re-run.\n")
