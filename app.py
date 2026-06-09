"""
SearchIQ — Streamlit demo app
Interactive UI for the full 4-agent pipeline.

Usage:
    streamlit run app.py

Shows:
  - Role brief input
  - Live agent progress with status indicators
  - Market map display
  - Profile cards with critique scores
  - Batch summary and export
"""

import os
import sys
import json
import time
from pathlib import Path

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SearchIQ",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.conf-high   { background:#d4edda; color:#155724; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
.conf-medium { background:#fff3cd; color:#856404; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
.conf-low    { background:#f8d7da; color:#721c24; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
.action-keep   { background:#d4edda; color:#155724; padding:2px 8px; border-radius:4px; font-size:12px; }
.action-revise { background:#fff3cd; color:#856404; padding:2px 8px; border-radius:4px; font-size:12px; }
.action-drop   { background:#f8d7da; color:#721c24; padding:2px 8px; border-radius:4px; font-size:12px; }
.metric-box { background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; padding:16px; text-align:center; }
.section-header { font-size:13px; font-weight:600; color:#6c757d; text-transform:uppercase;
                  letter-spacing:0.05em; margin:1.5rem 0 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Default brief ─────────────────────────────────────────────────────────────
DEFAULT_BRIEF = """We are conducting an executive search for a Chief Financial Officer (CFO) at a Series C fintech company headquartered in San Francisco. The company provides embedded lending infrastructure for SMBs and has reached $120M ARR with 200 employees. They are preparing for a Series D raise of $150-200M within 18 months and targeting a path to IPO within 3-4 years.

Ideal candidate profile:
- 15+ years in finance with 5+ years in a CFO or VP Finance role
- Deep experience with capital markets: equity raises, debt facilities, or IPO preparation
- Background in fintech, payments, lending, or marketplace businesses strongly preferred
- Proven ability to build and scale a finance function from ~$100M to $500M+ ARR
- Strong FP&A foundation; able to partner closely with the CEO on strategy
- Experience with investor relations and board communication

Reporting directly to CEO. Board includes partners from Andreessen Horowitz and Sequoia."""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 SearchIQ")
    st.caption("AI-powered executive research co-pilot")
    st.divider()

    st.markdown("**Model configuration**")
    from config import AGENT1_PROVIDER, AGENT1_MODEL, AGENT2_PROVIDER, AGENT2_MODEL, AGENT3_MODEL
    st.markdown(f"Agent 1 `{AGENT1_MODEL.split('-')[1] if '-' in AGENT1_MODEL else AGENT1_MODEL}`  \nMarket mapping")
    st.markdown(f"Agent 2 `{AGENT2_MODEL.split('-')[1] if '-' in AGENT2_MODEL else AGENT2_MODEL}`  \nProfile generation")
    st.markdown(f"Agent 3 `{AGENT3_MODEL.split('-')[1] if '-' in AGENT3_MODEL else AGENT3_MODEL}`  \nProfile critique")
    st.divider()

    st.markdown("**About this project**")
    st.caption(
        "Built in 3 days as a demo for SPMB's AI Data Analyst role. "
        "Demonstrates multi-agent orchestration, prompt engineering, "
        "AI output evaluation, and structured deliverable production."
    )

    if st.button("Load example brief"):
        st.session_state["brief"] = DEFAULT_BRIEF


# ── Main ──────────────────────────────────────────────────────────────────────
st.title("SearchIQ")
st.markdown("*Executive talent research — from brief to evaluated pipeline in minutes*")
st.divider()

# Role brief input
brief = st.text_area(
    "Role brief",
    value=st.session_state.get("brief", DEFAULT_BRIEF),
    height=200,
    key="brief_input",
    placeholder="Paste a role brief here..."
)

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    num_profiles = st.slider("Profiles to generate", min_value=3, max_value=10, value=5)
with col2:
    run_full = st.button("▶  Run full pipeline", type="primary", use_container_width=True)
with col3:
    load_prev = st.button("📂  Load last run", use_container_width=True)

# Load previous results
if load_prev:
    prev = Path("outputs/day2_full_pipeline.json")
    if prev.exists():
        with open(prev) as f:
            st.session_state["results"] = json.load(f)
        st.success("Loaded last run from outputs/day2_full_pipeline.json")
    else:
        st.warning("No previous run found. Run the pipeline first.")

# Run pipeline
if run_full:
    if not brief.strip():
        st.error("Please enter a role brief.")
    else:
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not anthropic_key:
            st.error("ANTHROPIC_API_KEY not found in .env")
            st.stop()

        results = {}
        progress = st.progress(0, text="Starting pipeline...")

        # ── Agent 1 ──────────────────────────────────────────────────────────
        progress.progress(5, text="Agent 1 — mapping the market (Haiku)...")
        a1_status = st.status("Agent 1: Market Mapper", expanded=True)
        t0 = time.time()
        try:
            from agents.agent1_market_mapper import MarketMapperAgent
            mapper     = MarketMapperAgent(api_key=anthropic_key)
            market_map = mapper.run(brief)
            a1_time    = round(time.time() - t0, 1)
            results["market_map"] = market_map
            a1_status.update(
                label=f"✅ Agent 1: Market Mapper — {len(market_map['target_companies'])} companies mapped ({a1_time}s)",
                state="complete"
            )
            with a1_status:
                st.caption(f"Comp range: {market_map.get('comp_range','')}")
                st.caption(f"Search notes: {market_map.get('search_notes','')[:150]}...")
        except Exception as e:
            a1_status.update(label=f"❌ Agent 1 failed: {e}", state="error")
            st.stop()

        # ── Agent 2 ──────────────────────────────────────────────────────────
        progress.progress(30, text="Agent 2 — generating profiles (Sonnet)...")
        a2_status = st.status("Agent 2: Profile Generator", expanded=True)
        t0 = time.time()
        try:
            from agents.agent2_profile_generator import ProfileGeneratorAgent
            from config import DEFAULT_NUM_PROFILES
            generator = ProfileGeneratorAgent(api_key=anthropic_key, num_profiles=num_profiles)
            profiles  = generator.run(brief, market_map)
            a2_time   = round(time.time() - t0, 1)
            results["profiles"] = profiles
            a2_status.update(
                label=f"✅ Agent 2: Profile Generator — {len(profiles)} profiles generated ({a2_time}s)",
                state="complete"
            )
        except Exception as e:
            a2_status.update(label=f"❌ Agent 2 failed: {e}", state="error")
            st.stop()

        # ── Agent 3 ──────────────────────────────────────────────────────────
        progress.progress(65, text="Agent 3 — critiquing profiles (Sonnet)...")
        a3_status = st.status("Agent 3: Profile Critic", expanded=True)
        t0 = time.time()
        try:
            from agents.agent3_profile_critic import ProfileCriticAgent
            critic   = ProfileCriticAgent(api_key=anthropic_key)
            critique = critic.run(brief, profiles)
            a3_time  = round(time.time() - t0, 1)
            results["critique"] = critique
            flagged  = sum(1 for c in critique["critiques"] if c["action"] != "keep")
            a3_status.update(
                label=f"✅ Agent 3: Profile Critic — {flagged} flagged ({a3_time}s)",
                state="complete"
            )
        except Exception as e:
            a3_status.update(label=f"❌ Agent 3 failed: {e}", state="error")
            st.stop()

        # ── Agent 4 ──────────────────────────────────────────────────────────
        progress.progress(90, text="Agent 4 — exporting...")
        try:
            from agents.agent4_exporter import SheetsExporter
            exporter       = SheetsExporter()
            export_result  = exporter.run(profiles, critique)
            results["export"] = export_result
        except Exception as e:
            st.warning(f"Export warning: {e}")

        progress.progress(100, text="Pipeline complete!")
        results["role_brief"] = brief

        # Save for Load Last Run
        out = Path("outputs/day2_full_pipeline.json")
        out.parent.mkdir(exist_ok=True)
        with open(out, "w") as f:
            json.dump(results, f, indent=2)

        st.session_state["results"] = results
        st.success("Pipeline complete!")


# ── Results display ───────────────────────────────────────────────────────────
if "results" in st.session_state:
    res        = st.session_state["results"]
    market_map = res.get("market_map", {})
    profiles   = res.get("profiles", [])
    critique   = res.get("critique", {})
    crit_map   = {c["profile_id"]: c for c in critique.get("critiques", [])}
    summary    = critique.get("batch_summary", {})

    st.divider()

    # ── Summary metrics ───────────────────────────────────────────────────────
    keeps   = sum(1 for c in crit_map.values() if c.get("action") == "keep")
    revises = sum(1 for c in crit_map.values() if c.get("action") == "revise")
    drops   = sum(1 for c in crit_map.values() if c.get("action") == "drop")
    highs   = sum(1 for c in crit_map.values() if c.get("confidence") == "high")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Companies mapped",  len(market_map.get("target_companies", [])))
    m2.metric("Profiles generated", len(profiles))
    m3.metric("Ready to present",   keeps,   delta=None)
    m4.metric("Needs revision",      revises, delta=None)
    m5.metric("Drop",                drops,   delta=None)

    if summary:
        qual_color = {"strong": "🟢", "mixed": "🟡", "weak": "🔴"}.get(summary.get("overall_quality",""), "⚪")
        st.info(f"{qual_color} **Overall quality: {summary.get('overall_quality','').upper()}** — "
                f"Top 3: profiles {summary.get('top_3_profiles',[])} — "
                f"Pattern: *{summary.get('failure_pattern','')}*")

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_profiles, tab_market, tab_export = st.tabs([
        "📋 Profiles & Critique", "🗺️ Market Map", "📤 Export"
    ])

    # ── Profiles tab ─────────────────────────────────────────────────────────
    with tab_profiles:
        filter_action = st.multiselect(
            "Filter by action", ["keep", "revise", "drop"],
            default=["keep", "revise", "drop"]
        )

        filtered = [p for p in profiles
                    if crit_map.get(p["profile_id"], {}).get("action", "keep") in filter_action]

        for p in filtered:
            pid  = p["profile_id"]
            crit = crit_map.get(pid, {})
            conf = crit.get("confidence", "")
            act  = crit.get("action", "")

            conf_html = f'<span class="conf-{conf}">{conf.upper()}</span>' if conf else ""
            act_html  = f'<span class="action-{act}">{act.upper()}</span>'  if act  else ""

            with st.expander(
                f"#{pid} {p['name']} — {p['current_title']} @ {p['current_company']}",
                expanded=(act == "keep")
            ):
                st.markdown(f"{conf_html} {act_html}", unsafe_allow_html=True)

                if crit.get("reviewer_note"):
                    st.markdown(f"**Reviewer note:** {crit['reviewer_note']}")

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Career summary**")
                    st.caption(p.get("career_summary", ""))
                    st.markdown("**Why they fit**")
                    st.caption(p.get("why_they_fit", ""))
                    st.markdown("**Key credentials**")
                    for cred in p.get("key_credentials", []):
                        st.caption(f"• {cred}")

                with c2:
                    if crit.get("issues"):
                        st.markdown("**Issues flagged**")
                        for issue in crit["issues"]:
                            st.error(f"⚠ {issue}", icon=None)
                    if crit.get("strengths"):
                        st.markdown("**Strengths**")
                        for s in crit["strengths"]:
                            st.success(f"✓ {s}", icon=None)
                    st.markdown("**Questions to probe**")
                    for q in p.get("questions_to_probe", []):
                        st.caption(f"→ {q}")

    # ── Market map tab ────────────────────────────────────────────────────────
    with tab_market:
        if market_map:
            st.markdown(f"**Comp range:** {market_map.get('comp_range','')}")
            st.markdown(f"**Search notes:** {market_map.get('search_notes','')}")
            st.divider()

            for tier in ["primary", "secondary", "stretch"]:
                cos = [c for c in market_map.get("target_companies", [])
                       if c.get("tier") == tier]
                if cos:
                    st.markdown(f"<div class='section-header'>{tier} targets</div>",
                                unsafe_allow_html=True)
                    for co in cos:
                        with st.expander(co["name"]):
                            st.caption(co.get("rationale", ""))
                            st.markdown("**Titles to search:** " +
                                        ", ".join(co.get("suggested_titles", [])))

            st.divider()
            st.markdown("<div class='section-header'>Talent pools</div>",
                        unsafe_allow_html=True)
            for pool in market_map.get("talent_pools", []):
                with st.expander(pool["cluster_name"]):
                    st.caption(pool["description"])
                    st.markdown(f"**Why relevant:** {pool['why_relevant']}")

    # ── Export tab ────────────────────────────────────────────────────────────
    with tab_export:
        export_info = res.get("export", {})
        if export_info:
            dest = export_info.get("destination", "csv")
            if dest == "sheets":
                st.success(f"Google Sheet: {export_info.get('url_or_path','')}")
            else:
                csv_path = Path(export_info.get("url_or_path", ""))
                if csv_path.exists():
                    with open(csv_path) as f:
                        csv_data = f.read()
                    st.download_button(
                        "⬇  Download All Profiles CSV",
                        data=csv_data,
                        file_name=csv_path.name,
                        mime="text/csv",
                        use_container_width=True
                    )

        json_path = Path("outputs/day2_full_pipeline.json")
        if json_path.exists():
            with open(json_path) as f:
                json_data = f.read()
            st.download_button(
                "⬇  Download Full Pipeline JSON",
                data=json_data,
                file_name="searchiq_pipeline_output.json",
                mime="application/json",
                use_container_width=True
            )

        st.divider()
        st.markdown("**To enable Google Sheets export:**")
        st.code("""# Add to your .env:
GOOGLE_SHEETS_CREDS_PATH=/path/to/service_account.json
GOOGLE_SHEET_ID=your_sheet_id_here""", language="bash")
        st.caption("See README.md → Google Sheets Setup for full instructions.")
