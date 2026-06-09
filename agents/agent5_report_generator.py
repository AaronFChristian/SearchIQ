"""
SearchIQ — Agent 5: Report Generator
Model: Claude Sonnet 4.6

PURPOSE:
Takes the full Day 2 pipeline output (market map + profiles + critiques) and produces
a client-ready HTML executive search brief.

TWO-STEP DESIGN (interview talking point):
  Step 1 — Claude generates narrative prose (executive summary, slate analysis, next steps)
            as structured JSON. AI handles the qualitative synthesis.
  Step 2 — Python assembles the full HTML report from the narrative + raw pipeline data.
            Code handles layout, data rendering, and formatting precision.

This split guarantees: data is always accurate (Python reads it directly) AND
the narrative is intelligent (Claude synthesizes it). No hallucinated stats.

Output: outputs/reports/searchiq_brief_<timestamp>.html
        Print to PDF via browser Cmd+P for a client-ready PDF.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
from datetime import datetime
from config import AGENT5_MODEL, MAX_RETRIES, RETRY_DELAY
from utils import get_logger, extract_json, RunMetadata
from prompts.prompts import REPORT_GENERATOR_SYSTEM, REPORT_GENERATOR_USER

logger = get_logger("Agent5.ReportGen")

# ── CSS: kept as a module constant so no f-string brace escaping issues ──────

_REPORT_CSS = """
  :root {
    --navy:         #0E2040;
    --navy-mid:     #1B3870;
    --blue:         #1560BD;
    --blue-light:   #E8F0FE;
    --bg:           #F1F4F9;
    --surface:      #FFFFFF;
    --border:       #D1DAE8;
    --text:         #111827;
    --text-2:       #374151;
    --text-3:       #6B7280;
    --keep:         #15803D;
    --keep-bg:      #DCFCE7;
    --keep-bd:      #86EFAC;
    --revise:       #B45309;
    --revise-bg:    #FEF3C7;
    --revise-bd:    #FCD34D;
    --drop:         #B91C1C;
    --drop-bg:      #FEE2E2;
    --drop-bd:      #FCA5A5;
    --amber-bg:     #FFFBEB;
    --amber-bd:     #FDE68A;
    --amber-text:   #78350F;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
  }

  h1, h2, h3, .serif { font-family: 'Lora', Georgia, 'Times New Roman', serif; }

  /* ── Layout ── */
  .page { max-width: 900px; margin: 0 auto; padding: 0 24px 64px; }

  /* ── Report Header ── */
  .report-header {
    background: var(--navy);
    color: white;
    padding: 40px 48px;
    border-radius: 0 0 16px 16px;
    margin: 0 -24px 28px;
  }
  .header-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
  }
  .wordmark {
    font-family: 'Lora', serif;
    font-size: 12px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.55);
  }
  .header-stamp {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: rgba(255,255,255,0.4);
  }
  .header-rule {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.12);
    margin: 14px 0 20px;
  }
  .engagement-title {
    font-family: 'Lora', serif;
    font-size: 26px;
    font-weight: 600;
    line-height: 1.35;
    color: white;
    margin-bottom: 10px;
  }
  .engagement-meta {
    font-size: 12px;
    color: rgba(255,255,255,0.55);
    display: flex;
    gap: 20px;
  }
  .engagement-meta span::before { content: "· "; }
  .engagement-meta span:first-child::before { content: ""; }

  /* ── Stats Bar ── */
  .stats-bar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 28px;
  }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
  }
  .stat-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    margin-bottom: 5px;
  }
  .stat-value {
    font-family: 'Lora', serif;
    font-size: 28px;
    font-weight: 700;
    color: var(--navy);
    line-height: 1;
  }
  .stat-sub { font-size: 11px; color: var(--text-3); margin-top: 4px; }

  /* ── Section Shell ── */
  .section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 32px;
    margin-bottom: 20px;
  }
  .section-eyebrow {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--blue);
    font-weight: 700;
    margin-bottom: 10px;
  }
  .section-title {
    font-family: 'Lora', serif;
    font-size: 19px;
    font-weight: 600;
    color: var(--navy);
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }

  /* ── Prose ── */
  .prose p {
    color: var(--text-2);
    line-height: 1.8;
    margin-bottom: 14px;
    font-size: 13.5px;
  }
  .prose p:last-child { margin-bottom: 0; }

  /* ── Callout Box ── */
  .callout {
    background: var(--blue-light);
    border-left: 3px solid var(--blue);
    border-radius: 0 8px 8px 0;
    padding: 12px 18px;
    font-size: 13px;
    color: var(--navy);
    margin-bottom: 20px;
  }
  .callout strong { font-weight: 600; }

  /* ── Company chips ── */
  .tier-section { margin-bottom: 16px; }
  .tier-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    font-weight: 700;
    margin-bottom: 7px;
  }
  .chip-row { display: flex; flex-wrap: wrap; gap: 7px; }
  .chip {
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
  }
  .chip-primary   { background: #EEF2FF; color: #3730A3; border: 1px solid #C7D2FE; }
  .chip-secondary { background: #F0F9FF; color: #0369A1; border: 1px solid #BAE6FD; }
  .chip-stretch   { background: #F9FAFB; color: #374151; border: 1px solid #E5E7EB; }

  /* ── Talent Pools ── */
  .pool-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 6px;
  }
  .pool-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
  }
  .pool-name { font-weight: 600; font-size: 12px; color: var(--navy); margin-bottom: 6px; }
  .pool-desc { font-size: 11.5px; color: var(--text-2); line-height: 1.55; margin-bottom: 6px; }
  .pool-why  { font-size: 11px; color: var(--blue); font-style: italic; line-height: 1.45; }

  /* ── Slate quality badge ── */
  .quality-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 20px;
  }
  .quality-strong { background: var(--keep-bg);   color: var(--keep);   border: 1px solid var(--keep-bd); }
  .quality-mixed  { background: var(--revise-bg); color: var(--revise); border: 1px solid var(--revise-bd); }
  .quality-weak   { background: var(--drop-bg);   color: var(--drop);   border: 1px solid var(--drop-bd); }

  /* ── Candidate Card ── */
  .candidate-card {
    border: 1px solid var(--border);
    border-left: 5px solid;
    border-radius: 0 10px 10px 0;
    padding: 24px 24px 24px 22px;
    margin-bottom: 18px;
    background: var(--surface);
  }
  .candidate-card:last-child { margin-bottom: 0; }
  .candidate-card.conf-high   { border-left-color: #22C55E; }
  .candidate-card.conf-medium { border-left-color: #F59E0B; }
  .candidate-card.conf-low    { border-left-color: #EF4444; }

  .cand-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
    gap: 16px;
  }
  .cand-rank {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    margin-bottom: 3px;
  }
  .cand-name {
    font-family: 'Lora', serif;
    font-size: 20px;
    font-weight: 600;
    color: var(--navy);
    margin-bottom: 2px;
  }
  .cand-role { font-size: 12.5px; color: var(--text-2); }
  .badge-row { display: flex; gap: 7px; flex-shrink: 0; padding-top: 4px; }

  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .badge-high   { background: var(--keep-bg);   color: var(--keep);   border: 1px solid var(--keep-bd); }
  .badge-medium { background: var(--revise-bg); color: var(--revise); border: 1px solid var(--revise-bd); }
  .badge-low    { background: var(--drop-bg);   color: var(--drop);   border: 1px solid var(--drop-bd); }
  .badge-keep   { background: var(--keep-bg);   color: var(--keep);   border: 1px solid var(--keep-bd); }
  .badge-revise { background: var(--revise-bg); color: var(--revise); border: 1px solid var(--revise-bd); }
  .badge-drop   { background: var(--drop-bg);   color: var(--drop);   border: 1px solid var(--drop-bd); }

  .cand-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }
  .sub-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    font-weight: 700;
    margin-bottom: 7px;
    margin-top: 16px;
  }
  .sub-label:first-child { margin-top: 0; }
  .sub-text { font-size: 12.5px; color: var(--text-2); line-height: 1.65; }

  .cred-list { list-style: none; padding: 0; }
  .cred-list li {
    font-size: 12px;
    color: var(--text-2);
    padding: 5px 0 5px 18px;
    position: relative;
    line-height: 1.5;
    border-bottom: 1px solid var(--bg);
  }
  .cred-list li:last-child { border-bottom: none; }
  .cred-list li::before {
    content: "→";
    position: absolute;
    left: 0;
    color: var(--blue);
    font-size: 10px;
    top: 7px;
  }

  .issue-item, .strength-item {
    border-radius: 6px;
    padding: 7px 11px;
    margin-bottom: 6px;
    font-size: 12px;
    line-height: 1.55;
  }
  .issue-item    { background: #FFF5F5; border: 1px solid #FECACA; color: #7F1D1D; }
  .strength-item { background: #F0FDF4; border: 1px solid #BBF7D0; color: #14532D; }

  .probe-list { list-style: none; padding: 0; }
  .probe-list li {
    font-size: 12px;
    color: var(--text-2);
    padding: 5px 0 5px 22px;
    position: relative;
    line-height: 1.55;
    border-bottom: 1px solid var(--bg);
  }
  .probe-list li:last-child { border-bottom: none; }
  .probe-marker {
    position: absolute;
    left: 0;
    top: 6px;
    width: 15px;
    height: 15px;
    background: var(--blue);
    color: white;
    font-size: 9px;
    font-weight: 700;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .reviewer-note {
    background: var(--amber-bg);
    border: 1px solid var(--amber-bd);
    border-radius: 7px;
    padding: 10px 14px;
    margin-top: 16px;
    font-size: 12px;
    color: var(--amber-text);
    font-style: italic;
    line-height: 1.6;
  }
  .reviewer-note-label {
    font-style: normal;
    font-weight: 700;
    margin-right: 4px;
  }

  /* ── All-profiles table ── */
  .profiles-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
  .profiles-table th {
    background: var(--navy);
    color: rgba(255,255,255,0.85);
    padding: 9px 11px;
    text-align: left;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
  }
  .profiles-table th:first-child { border-radius: 6px 0 0 0; }
  .profiles-table th:last-child  { border-radius: 0 6px 0 0; }
  .profiles-table td {
    padding: 10px 11px;
    border-bottom: 1px solid var(--border);
    color: var(--text-2);
    vertical-align: top;
    line-height: 1.5;
  }
  .profiles-table tr:last-child td { border-bottom: none; }
  .profiles-table tr:hover td { background: var(--bg); }

  /* ── Failure pattern callout ── */
  .failure-callout {
    background: #FFF7ED;
    border: 1px solid #FED7AA;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 20px;
  }
  .failure-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #C2410C;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .failure-text { font-size: 13px; color: #7C2D12; line-height: 1.65; }

  /* ── Next steps ── */
  .steps-list { list-style: none; padding: 0; }
  .step-item {
    display: grid;
    grid-template-columns: 38px 1fr;
    gap: 14px;
    margin-bottom: 22px;
    align-items: flex-start;
  }
  .step-item:last-child { margin-bottom: 0; }
  .step-num {
    width: 38px;
    height: 38px;
    background: var(--navy);
    color: white;
    font-family: 'Lora', serif;
    font-size: 17px;
    font-weight: 700;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .step-body { padding-top: 3px; }
  .step-title { font-weight: 600; font-size: 14px; color: var(--navy); margin-bottom: 4px; }
  .step-detail { font-size: 13px; color: var(--text-2); line-height: 1.65; }

  /* ── Footer ── */
  .report-footer {
    text-align: center;
    padding: 28px 0 16px;
    border-top: 1px solid var(--border);
    margin-top: 28px;
  }
  .footer-brand { font-family: 'Lora', serif; font-size: 12px; color: var(--text-3); letter-spacing: 0.12em; text-transform: uppercase; }
  .footer-meta  { font-size: 11px; color: var(--text-3); margin-top: 5px; }

  /* ── Divider ── */
  .sub-divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }

  /* ── Print ── */
  @media print {
    body { background: white; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .page { padding: 0 32px 32px; }
    .report-header { border-radius: 0; margin: 0 -32px 24px; }
    .section { box-shadow: none; page-break-inside: avoid; }
    .candidate-card { page-break-inside: avoid; }
    .stats-bar { page-break-inside: avoid; }
  }
"""


class ReportGeneratorAgent:

    def __init__(self, api_key: str):
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install anthropic")
        logger.info(f"ReportGeneratorAgent | model={AGENT5_MODEL}")

    # ── HTML helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _e(text) -> str:
        """HTML-escape a value."""
        return (str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    def _badge(self, conf: str) -> str:
        cls = {"high": "badge-high", "medium": "badge-medium", "low": "badge-low"}.get(conf, "")
        label = conf.upper() if conf else "?"
        return f'<span class="badge {cls}">{self._e(label)}</span>'

    def _action_badge(self, action: str) -> str:
        cls = {"keep": "badge-keep", "revise": "badge-revise", "drop": "badge-drop"}.get(action, "")
        return f'<span class="badge {cls}">{self._e(action.upper() if action else "?")}</span>'

    # ── Claude call ──────────────────────────────────────────────────────────

    def _build_profiles_summary(self, profiles: list, crit_map: dict) -> str:
        lines = []
        for p in profiles:
            pid  = p.get("profile_id")
            crit = crit_map.get(pid, {})
            conf = crit.get("confidence", "?")
            act  = crit.get("action", "?")
            lines.append(
                f"  #{pid}: {p.get('name')} — {p.get('current_title')} @ "
                f"{p.get('current_company')} [{conf}/{act}]"
            )
        return "\n".join(lines)

    def _call_claude(self, pipeline_data: dict) -> tuple[dict, int]:
        """Calls Claude Sonnet to generate narrative prose sections."""
        market_map    = pipeline_data.get("market_map", {})
        profiles      = pipeline_data.get("profiles", [])
        critique      = pipeline_data.get("critique", {})
        batch_summary = critique.get("batch_summary", {})
        crit_map      = {c["profile_id"]: c for c in critique.get("critiques", [])}

        # Company summary for prompt (tier-grouped)
        companies = market_map.get("target_companies", [])
        primary   = [c["name"] for c in companies if c.get("tier") == "primary"]
        secondary = [c["name"] for c in companies if c.get("tier") == "secondary"]
        co_summary = (f"Primary: {', '.join(primary[:5])}. "
                      f"Secondary: {', '.join(secondary[:4])}")

        prompt = REPORT_GENERATOR_USER.format(
            role_brief      = pipeline_data.get("role_brief", ""),
            comp_range      = market_map.get("comp_range", ""),
            search_notes    = market_map.get("search_notes", ""),
            company_summary = co_summary,
            num_profiles    = len(profiles),
            overall_quality = batch_summary.get("overall_quality", ""),
            top_3_ids       = batch_summary.get("top_3_profiles", []),
            failure_pattern = batch_summary.get("failure_pattern", ""),
            profiles_summary= self._build_profiles_summary(profiles, crit_map),
        )

        response = self._client.messages.create(
            model=AGENT5_MODEL,
            max_tokens=3000,
            system=REPORT_GENERATOR_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        text   = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return extract_json(text), tokens

    def _validate(self, narrative: dict) -> list[str]:
        errors = []
        for key in ["engagement_title", "executive_summary", "slate_analysis", "next_steps"]:
            if key not in narrative:
                errors.append(f"Missing key: '{key}'")
        if "next_steps" in narrative:
            if not isinstance(narrative["next_steps"], list) or len(narrative["next_steps"]) < 2:
                errors.append("'next_steps' must be a list with at least 2 items")
            for step in narrative.get("next_steps", []):
                if not isinstance(step, dict) or "title" not in step or "detail" not in step:
                    errors.append("Each next_step must have 'title' and 'detail'")
                    break
        return errors

    # ── HTML rendering ───────────────────────────────────────────────────────

    def _render_head(self) -> str:
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n<head>\n'
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            "<title>SearchIQ Executive Search Brief</title>\n"
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;600;700&'
            'family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">\n'
            f"<style>{_REPORT_CSS}</style>\n"
            "</head>\n<body>\n<div class=\"page\">\n"
        )

    def _render_header(self, pipeline_data: dict, narrative: dict) -> str:
        title   = self._e(narrative.get("engagement_title", "Executive Search Brief"))
        date_s  = datetime.now().strftime("%B %d, %Y")
        n_prof  = len(pipeline_data.get("profiles", []))
        quality = pipeline_data.get("critique", {}).get("batch_summary", {}).get("overall_quality", "")

        return (
            '<div class="report-header">\n'
            '  <div class="header-meta">\n'
            '    <div class="wordmark">SearchIQ</div>\n'
            f'    <div class="header-stamp">Executive Search Brief &nbsp;·&nbsp; {date_s}</div>\n'
            "  </div>\n"
            '  <hr class="header-rule">\n'
            f'  <div class="engagement-title">{title}</div>\n'
            '  <div class="engagement-meta">\n'
            f'    <span>Prepared for Review</span>\n'
            f'    <span>{n_prof} Candidates Evaluated</span>\n'
            f'    <span>Slate Quality: {quality.upper() if quality else "—"}</span>\n'
            f'    <span>Generated {date_s}</span>\n'
            "  </div>\n"
            "</div>\n"
        )

    def _render_stats_bar(self, pipeline_data: dict) -> str:
        critique  = pipeline_data.get("critique", {})
        critiques = critique.get("critiques", [])
        profiles  = pipeline_data.get("profiles", [])
        mkt       = pipeline_data.get("market_map", {})

        keeps   = sum(1 for c in critiques if c.get("action") == "keep")
        revises = sum(1 for c in critiques if c.get("action") == "revise")
        highs   = sum(1 for c in critiques if c.get("confidence") == "high")
        n_cos   = len(mkt.get("target_companies", []))
        quality = critique.get("batch_summary", {}).get("overall_quality", "—")
        qual_cls = {"strong": "quality-strong", "mixed": "quality-mixed", "weak": "quality-weak"}.get(quality, "")
        qual_icon = {"strong": "●", "mixed": "◑", "weak": "○"}.get(quality, "—")

        def stat(label, value, sub=""):
            sub_html = f'<div class="stat-sub">{self._e(sub)}</div>' if sub else ""
            return (
                '<div class="stat-card">\n'
                f'  <div class="stat-label">{label}</div>\n'
                f'  <div class="stat-value">{value}</div>\n'
                f'  {sub_html}\n'
                "</div>\n"
            )

        return (
            '<div class="stats-bar">\n'
            + stat("Companies Mapped", n_cos, "target universe")
            + stat("Profiles Generated", len(profiles), "synthetic slate")
            + stat("Ready to Present", keeps, f"{revises} needs revision")
            + stat("High Confidence", highs, f"slate: {quality.upper()}")
            + "</div>\n"
        )

    def _render_executive_summary(self, narrative: dict) -> str:
        raw  = narrative.get("executive_summary", "")
        paras= [p.strip() for p in raw.split("\n\n") if p.strip()]
        body = "\n".join(f"<p>{self._e(p)}</p>" for p in paras)
        return (
            '<div class="section">\n'
            '  <div class="section-eyebrow">01 / Executive Summary</div>\n'
            '  <div class="section-title">Search Overview</div>\n'
            f'  <div class="prose">{body}</div>\n'
            "</div>\n"
        )

    def _render_market_intel(self, pipeline_data: dict) -> str:
        mkt    = pipeline_data.get("market_map", {})
        comp   = self._e(mkt.get("comp_range", ""))
        notes  = self._e(mkt.get("search_notes", ""))
        companies = mkt.get("target_companies", [])
        pools  = mkt.get("talent_pools", [])

        # Comp callout
        comp_html = (
            f'  <div class="callout"><strong>Compensation Range:</strong> {comp}</div>\n'
        )

        # Company chips by tier
        tiers = [
            ("primary",   "Primary Targets",   "chip-primary"),
            ("secondary", "Secondary Targets",  "chip-secondary"),
            ("stretch",   "Stretch Targets",    "chip-stretch"),
        ]
        chips_html = ""
        for tier_key, tier_label, chip_cls in tiers:
            cos = [c for c in companies if c.get("tier") == tier_key]
            if not cos:
                continue
            row = " ".join(
                f'<span class="chip {chip_cls}" title="{self._e(c.get("rationale",""))}">'
                f'{self._e(c["name"])}</span>'
                for c in cos
            )
            chips_html += (
                f'  <div class="tier-section">\n'
                f'    <div class="tier-label">{tier_label}</div>\n'
                f'    <div class="chip-row">{row}</div>\n'
                f'  </div>\n'
            )

        # Talent pools
        pool_cards = ""
        for pool in pools:
            pool_cards += (
                '  <div class="pool-card">\n'
                f'    <div class="pool-name">{self._e(pool.get("cluster_name",""))}</div>\n'
                f'    <div class="pool-desc">{self._e(pool.get("description",""))}</div>\n'
                f'    <div class="pool-why">{self._e(pool.get("why_relevant",""))}</div>\n'
                "  </div>\n"
            )

        # Search notes
        notes_html = (
            f'  <hr class="sub-divider">\n'
            f'  <div class="section-eyebrow" style="margin-bottom:8px">Search Strategy</div>\n'
            f'  <p class="sub-text" style="font-size:13px;color:var(--text-2);line-height:1.75">{notes}</p>\n'
        )

        return (
            '<div class="section">\n'
            '  <div class="section-eyebrow">02 / Market Intelligence</div>\n'
            '  <div class="section-title">Talent Market Overview</div>\n'
            + comp_html
            + '<div style="margin-bottom:20px">\n'
            + '  <div class="section-eyebrow" style="margin-bottom:10px">Target Company Universe</div>\n'
            + chips_html
            + "</div>\n"
            + '  <hr class="sub-divider">\n'
            + '  <div class="section-eyebrow" style="margin-bottom:10px">Talent Pools</div>\n'
            + '  <div class="pool-grid">\n' + pool_cards + "  </div>\n"
            + notes_html
            + "</div>\n"
        )

    def _render_candidate_card(self, profile: dict, critique: dict | None, rank: int) -> str:
        crit  = critique or {}
        conf  = crit.get("confidence", "")
        act   = crit.get("action", "")
        pid   = profile.get("profile_id", rank)

        # Header
        rank_labels = {1: "★ Top Recommendation", 2: "★★ Second Recommendation", 3: "★★★ Third Recommendation"}
        rank_label  = rank_labels.get(rank, f"Candidate #{pid}")
        header = (
            '  <div class="cand-top">\n'
            "    <div>\n"
            f'      <div class="cand-rank">{self._e(rank_label)}</div>\n'
            f'      <div class="cand-name">{self._e(profile.get("name",""))}</div>\n'
            f'      <div class="cand-role">{self._e(profile.get("current_title",""))}'
            f' &nbsp;·&nbsp; {self._e(profile.get("current_company",""))}</div>\n'
            "    </div>\n"
            '    <div class="badge-row">\n'
            f'      {self._badge(conf)}\n'
            f'      {self._action_badge(act)}\n'
            "    </div>\n"
            "  </div>\n"
        )

        # Left col: career summary + key credentials + why they fit
        creds_li = "\n".join(
            f'  <li>{self._e(c)}</li>'
            for c in profile.get("key_credentials", [])
        )
        left = (
            "    <div>\n"
            '      <div class="sub-label">Career Summary</div>\n'
            f'      <p class="sub-text">{self._e(profile.get("career_summary",""))}</p>\n'
            '      <div class="sub-label">Key Credentials</div>\n'
            f'      <ul class="cred-list">{creds_li}</ul>\n'
            '      <div class="sub-label">Why They Fit</div>\n'
            f'      <p class="sub-text">{self._e(profile.get("why_they_fit",""))}</p>\n'
            "    </div>\n"
        )

        # Right col: issues + strengths + probe questions
        issues_html    = "\n".join(
            f'      <div class="issue-item">{self._e(i)}</div>'
            for i in crit.get("issues", [])
        )
        strengths_html = "\n".join(
            f'      <div class="strength-item">{self._e(s)}</div>'
            for s in crit.get("strengths", [])
        )
        probes_li = "\n".join(
            f'  <li><span class="probe-marker">?</span>{self._e(q)}</li>'
            for q in profile.get("questions_to_probe", [])
        )
        right = (
            "    <div>\n"
            '      <div class="sub-label">Issues to Address</div>\n'
            + (issues_html or '      <div class="issue-item">No issues flagged</div>')
            + '\n      <div class="sub-label">Strengths</div>\n'
            + (strengths_html or '      <div class="strength-item">Not evaluated</div>')
            + '\n      <div class="sub-label">Questions to Probe</div>\n'
            + f'      <ul class="probe-list">{probes_li}</ul>\n'
            + "    </div>\n"
        )

        # Reviewer note
        note = crit.get("reviewer_note", "")
        note_html = (
            f'  <div class="reviewer-note">'
            f'<span class="reviewer-note-label">Reviewer note:</span> {self._e(note)}</div>\n'
        ) if note else ""

        conf_cls = f"conf-{conf}" if conf else ""
        return (
            f'<div class="candidate-card {conf_cls}">\n'
            + header
            + '<div class="cand-body">\n'
            + left + right
            + "</div>\n"
            + note_html
            + "</div>\n"
        )

    def _render_candidate_slate(self, pipeline_data: dict, narrative: dict) -> str:
        critique  = pipeline_data.get("critique", {})
        profiles  = pipeline_data.get("profiles", [])
        batch_sum = critique.get("batch_summary", {})
        crit_map  = {c["profile_id"]: c for c in critique.get("critiques", [])}
        prof_map  = {p["profile_id"]: p for p in profiles}

        top3_ids = batch_sum.get("top_3_profiles", [])
        top3: list[tuple] = []
        for pid in top3_ids:
            if pid in prof_map:
                top3.append((prof_map[pid], crit_map.get(pid)))
        # Pad if < 3 (fallback: first profiles)
        for p in profiles:
            if len(top3) >= 3:
                break
            if not any(t[0]["profile_id"] == p["profile_id"] for t in top3):
                top3.append((p, crit_map.get(p["profile_id"])))

        quality  = batch_sum.get("overall_quality", "")
        qual_cls = {"strong": "quality-strong", "mixed": "quality-mixed", "weak": "quality-weak"}.get(quality, "")
        qual_dot = {"strong": "● STRONG", "mixed": "◑ MIXED", "weak": "○ WEAK"}.get(quality, quality.upper())

        cards_html = "\n".join(
            self._render_candidate_card(prof, crit, rank + 1)
            for rank, (prof, crit) in enumerate(top3)
        )

        return (
            '<div class="section">\n'
            '  <div class="section-eyebrow">03 / Candidate Slate</div>\n'
            '  <div class="section-title">Top Recommended Candidates</div>\n'
            f'  <div class="quality-badge {qual_cls}">{qual_dot} Slate</div>\n'
            + cards_html
            + "</div>\n"
        )

    def _render_slate_analysis(self, pipeline_data: dict, narrative: dict) -> str:
        critique  = pipeline_data.get("critique", {})
        profiles  = pipeline_data.get("profiles", [])
        critiques = critique.get("critiques", [])
        crit_map  = {c["profile_id"]: c for c in critiques}
        prof_map  = {p["profile_id"]: p for p in profiles}
        batch_sum = critique.get("batch_summary", {})

        # AI narrative
        slate_text = narrative.get("slate_analysis", "")
        slate_html = f'<p class="sub-text" style="font-size:13.5px;color:var(--text-2);line-height:1.8;margin-bottom:20px">{self._e(slate_text)}</p>'

        # All profiles table
        rows = ""
        for p in sorted(profiles, key=lambda x: x.get("profile_id", 0)):
            pid  = p.get("profile_id")
            crit = crit_map.get(pid, {})
            conf = crit.get("confidence", "")
            act  = crit.get("action", "")
            note = crit.get("reviewer_note", "—")
            rows += (
                f"  <tr>\n"
                f'    <td style="font-weight:600;white-space:nowrap">#{pid} {self._e(p.get("name",""))}</td>\n'
                f'    <td>{self._e(p.get("current_title",""))}</td>\n'
                f'    <td>{self._e(p.get("current_company",""))}</td>\n'
                f'    <td>{self._badge(conf)}</td>\n'
                f'    <td>{self._action_badge(act)}</td>\n'
                f'    <td style="font-size:11.5px;font-style:italic">{self._e(note)}</td>\n'
                "  </tr>\n"
            )

        table = (
            '<table class="profiles-table">\n'
            "  <thead><tr>\n"
            "    <th>Candidate</th><th>Title</th><th>Company</th>"
            "<th>Confidence</th><th>Action</th><th>Reviewer Note</th>\n"
            "  </tr></thead>\n"
            f"  <tbody>{rows}</tbody>\n"
            "</table>\n"
        )

        failure_pattern = batch_sum.get("failure_pattern", "")
        failure_html = (
            '<div class="failure-callout">\n'
            '  <div class="failure-label">Common Failure Pattern</div>\n'
            f'  <div class="failure-text">{self._e(failure_pattern)}</div>\n'
            "</div>\n"
        ) if failure_pattern else ""

        return (
            '<div class="section">\n'
            '  <div class="section-eyebrow">04 / Slate Quality Analysis</div>\n'
            '  <div class="section-title">Full Candidate Assessment</div>\n'
            + slate_html
            + table
            + failure_html
            + "</div>\n"
        )

    def _render_next_steps(self, narrative: dict) -> str:
        steps = narrative.get("next_steps", [])
        steps_html = ""
        for i, step in enumerate(steps, 1):
            if isinstance(step, dict):
                title  = self._e(step.get("title", ""))
                detail = self._e(step.get("detail", ""))
            else:
                # handle plain strings as fallback
                title  = self._e(str(step))
                detail = ""

            detail_html = f'<div class="step-detail">{detail}</div>' if detail else ""
            steps_html += (
                '<li class="step-item">\n'
                f'  <div class="step-num">{i}</div>\n'
                "  <div class=\"step-body\">\n"
                f'    <div class="step-title">{title}</div>\n'
                f'    {detail_html}\n'
                "  </div>\n"
                "</li>\n"
            )

        return (
            '<div class="section">\n'
            '  <div class="section-eyebrow">05 / Recommended Next Steps</div>\n'
            '  <div class="section-title">Search Progression Plan</div>\n'
            f'  <ul class="steps-list">{steps_html}</ul>\n'
            "</div>\n"
        )

    def _render_footer(self) -> str:
        date_s = datetime.now().strftime("%B %d, %Y at %H:%M")
        return (
            '<div class="report-footer">\n'
            '  <div class="footer-brand">SearchIQ</div>\n'
            f'  <div class="footer-meta">Generated by SearchIQ AI Pipeline &nbsp;·&nbsp; {date_s}'
            " &nbsp;·&nbsp; Confidential — For Review Purposes Only</div>\n"
            "</div>\n"
        )

    def _render_html(self, pipeline_data: dict, narrative: dict) -> str:
        parts = [
            self._render_head(),
            self._render_header(pipeline_data, narrative),
            self._render_stats_bar(pipeline_data),
            self._render_executive_summary(narrative),
            self._render_market_intel(pipeline_data),
            self._render_candidate_slate(pipeline_data, narrative),
            self._render_slate_analysis(pipeline_data, narrative),
            self._render_next_steps(narrative),
            self._render_footer(),
            "</div>\n</body>\n</html>",
        ]
        return "\n".join(parts)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self, html: str) -> Path:
        out_dir = Path("outputs/reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"searchiq_brief_{ts}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Report saved → {path}")
        return path

    # ── Main entry point ─────────────────────────────────────────────────────

    def run(self, pipeline_data: dict,
            metadata: RunMetadata | None = None) -> dict:
        """
        Takes full pipeline output dict, generates narrative via Claude,
        renders HTML, saves to outputs/reports/.

        Returns:
            {
              "html_path":  str path to HTML file,
              "tokens":     int tokens used,
              "engagement": str engagement title,
            }
        """
        logger.info("Generating search brief narrative via Claude...")
        start      = time.time()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 2):
            try:
                logger.debug(f"Attempt {attempt} — calling Claude for narrative...")
                narrative, tokens = self._call_claude(pipeline_data)

                errors = self._validate(narrative)
                if errors:
                    err_str = "\n".join(f"  - {e}" for e in errors)
                    logger.warning(f"Narrative validation failed (attempt {attempt}):\n{err_str}")
                    if attempt <= MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                        continue
                    raise ValueError(f"Report narrative failed validation:\n{err_str}")

                logger.info(f"Narrative generated | {tokens} tokens | rendering HTML...")
                html     = self._render_html(pipeline_data, narrative)
                path     = self._save(html)
                duration = round(time.time() - start, 2)

                logger.info(f"Report complete | {duration}s | {len(html):,} chars | {path}")

                if metadata:
                    metadata.record("Agent5.ReportGen", "ok", duration, tokens)

                return {
                    "html_path":  str(path),
                    "tokens":     tokens,
                    "engagement": narrative.get("engagement_title", ""),
                    "html":       html,
                }

            except ValueError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt} error: {e}")
                if attempt <= MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        duration = round(time.time() - start, 2)
        if metadata:
            metadata.record("Agent5.ReportGen", "failed", duration)
        raise RuntimeError(f"Agent5 failed after all retries. Last error: {last_error}")
