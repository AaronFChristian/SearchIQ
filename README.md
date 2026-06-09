# SearchIQ

**AI-powered executive research co-pilot** — from role brief to evaluated candidate pipeline in under 5 minutes.

Built in 3 days as a demonstration project for SPMB's AI Data Analyst role.

---

## What it does

SearchIQ runs a 4-agent pipeline that automates the most time-intensive parts of an executive search:

1. **Market Mapper (Agent 1)** — takes a role brief and returns a tiered company target list, talent pools, comp range, and search notes
2. **Profile Generator (Agent 2)** — generates 10 realistic executive profiles drawn from the market map
3. **Profile Critic (Agent 3)** — evaluates every profile against the brief: confidence score, action recommendation, specific issues, and a one-line tracker note
4. **Exporter (Agent 4)** — merges profiles + critique into Google Sheets or CSV (All Profiles + Flagged tabs)

This isn't a replacement for Lee or any existing platform. It's a research co-pilot that runs *before* sourcing — compressing 2–3 hours of manual market research into a structured, human-reviewable deliverable.

---

## Sample output

**Role brief used:** CFO search at a Series C fintech ($120M ARR, SMB embedded lending, Series D + IPO path)

**Agent 1 output (excerpt):**
```
Comp range: $425k–$575k base + 15–25% bonus + 1.0–1.5% fully diluted equity
Primary targets: Stripe, Brex, Affirm, Pipe
Talent pools: Series C/D Fintech CFOs, Big-4 Fintech M&A, Late-Stage SaaS Finance Leaders
```

**Agent 3 batch summary:**
```
Overall quality: MIXED
Top 3 to present: #2 Marcus Delacroix, #7 Sandra Okafor, #5 Priya Nambiar
Failure pattern: Seniority inflation — profiles present VP Finance candidates as CFO-ready
  by emphasizing employer scope rather than candidate's own independent accountability
```

**Agent 3 catch (factual error):**
```
Profile #10 — Nathaniel Rosenberg
Issue: Kabbage acquisition price stated as $135M — actual American Express acquisition
  was $850M. A partner from a16z or Sequoia who knows the transaction will immediately
  flag this, raising questions about research quality of the entire slate.
Action: REVISE
```

---

## Architecture

```
Role brief
    │
    ▼
Agent 1 — Market Mapper        claude-haiku-4-5
    │  target companies, talent pools, comp range
    ▼
Agent 2 — Profile Generator    claude-sonnet-4-6
    │  10 profiles with credentials, fit assessment, probe questions
    ▼
Agent 3 — Profile Critic       claude-sonnet-4-6
    │  confidence scores, issue flags, reviewer notes, batch summary
    ▼
Agent 4 — Exporter
    │  Google Sheets (3 tabs) or CSV fallback
    ▼
outputs/day2_full_pipeline.json
```

**Why different models per agent:**
- `claude-haiku-4-5` for Agent 1 — fast and cheap for broad synthesis; market mapping doesn't need deep reasoning
- `claude-sonnet-4-6` for Agents 2 + 3 — stronger instruction-following for schema-bound generation, and better evaluative reasoning for critique
- Architecture is provider-agnostic: swap `AGENT1_PROVIDER = "gemini"` in `config.py` to route Agent 1 through Gemini 2.0 Flash once the Generative Language API is enabled

---

## Prompt engineering — v1 vs v2

Every prompt is versioned in `prompts/prompts.py`. Here's what changed and why:

### Agent 1 — Market Mapper

**v1 problem:** returned generic companies (Goldman Sachs, McKinsey) regardless of the brief. Flat list with no prioritisation.

**v2 changes:**
- Added `"tier": "primary" | "secondary" | "stretch"` — forces prioritisation signal
- Added `"suggested_titles"` per company — makes the map actionable immediately
- Added specificity constraint: *"prefer $500M–$5B companies unless brief specifies otherwise"*
- Added `comp_range` and `search_notes` fields — v1 had no salary or focus guidance

### Agent 2 — Profile Generator

**v1 problem:** `why_they_fit` was generic ("strong financial background, leadership experience") — applied to every candidate identically.

**v2 changes:**
- Made `why_they_fit` explicitly brief-specific with a good/bad example in the prompt
- Added `questions_to_probe` field — forces gap analysis, not just promotional summary
- Added "no vague claims" constraint with examples: *"good → Led $2.1B Series D... / bad → Extensive experience in capital markets"*
- Passed `market_map` as context — profiles now draw from the target company list

### Agent 3 — Profile Critic

**v1 problem:** issues were generic strings ("limited experience"), no recommended action, no batch-level pattern detection.

**v2 changes:**
- Added `"action": "keep" | "revise" | "drop"` — gives the analyst a concrete next step
- Added `"reviewer_note"` — one sentence matching what you'd write in a search tracker (e.g. Thrive)
- Required specificity in issues with good/bad examples in the system prompt
- Added `batch_summary.failure_pattern` — systemic diagnosis across the set, not just individual flags

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yourname/searchiq
cd searchiq
pip install anthropic openai google-genai gspread python-dotenv streamlit
```

### 2. API keys

Copy `.env.example` to `.env` and add your keys:

```
ANTHROPIC_API_KEY=sk-ant-...     # required
GEMINI_API_KEY=AIza...           # optional upgrade for Agent 1
OPENAI_API_KEY=sk-proj-...       # optional upgrade for Agent 2
```

Validate keys:
```bash
python check_keys.py
```

### 3. Run the pipeline

**Day 1 — Market map + profiles:**
```bash
python run_day1.py
```

**Day 2 — Critique + export:**
```bash
python run_day2.py
```

**Interactive UI:**
```bash
streamlit run app.py
```

---

## Google Sheets setup (optional)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → APIs → Enable **Google Sheets API** and **Google Drive API**
2. Create a Service Account → download the JSON credentials file
3. Create a Google Sheet and share it with the service account email (Editor access)
4. Add to `.env`:
   ```
   GOOGLE_SHEETS_CREDS_PATH=/path/to/service_account.json
   GOOGLE_SHEET_ID=your_sheet_id
   ```

Without this, `run_day2.py` and `app.py` automatically write CSV to `outputs/`.

---

## Enabling Gemini (Agent 1 upgrade)

If Agent 1 returns `API key not valid`:
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Select the project linked to your key
3. Search **Generative Language API** → Enable
4. Wait 60 seconds, then in `config.py`:
   ```python
   AGENT1_PROVIDER = "gemini"
   AGENT1_MODEL    = "gemini-2.0-flash"
   ```

---

## Project structure

```
searchiq/
├── app.py                          # Streamlit UI
├── run_day1.py                     # CLI: Agent 1 + 2
├── run_day2.py                     # CLI: Agent 3 + 4 (loads day1 output)
├── check_keys.py                   # API key validator
├── config.py                       # Model assignments + provider switches
├── utils.py                        # JSON extractor, retry logic, run logger
├── agents/
│   ├── agent1_market_mapper.py     # Gemini or Claude
│   ├── agent2_profile_generator.py # OpenAI or Claude
│   ├── agent3_profile_critic.py    # Claude Sonnet
│   └── agent4_exporter.py          # Google Sheets + CSV
├── prompts/
│   └── prompts.py                  # All prompts, versioned with v1→v2 diffs
├── schemas/
│   └── schemas.py                  # JSON contracts between agents
└── outputs/                        # Pipeline outputs (gitignored)
```

---

## What I'd build next

- **Web scraping layer** before Agent 1: pull real company headcount, funding rounds, and recent finance hire signals from LinkedIn/Crunchbase to ground the market map in live data
- **Candidate verification agent**: cross-reference profile credentials against public sources (LinkedIn, SEC filings, press releases) — catches the Kabbage price error automatically
- **Prompt eval framework**: systematic testing of prompt versions across 20+ briefs with quality scoring, so iteration is data-driven rather than intuition-driven
- **Integration with ATS/CRM** (e.g. Thrive): auto-populate reviewer notes and confidence scores directly into the search tracker after critique

---

## Built with

- [Anthropic Claude](https://anthropic.com) — claude-haiku-4-5, claude-sonnet-4-6
- [Google Gemini](https://aistudio.google.com) — gemini-2.0-flash (optional)
- [OpenAI](https://platform.openai.com) — gpt-4o-mini (optional)
- [Streamlit](https://streamlit.io) — demo UI
- [gspread](https://github.com/burnash/gspread) — Google Sheets export
