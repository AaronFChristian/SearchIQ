"""
SearchIQ — JSON schemas for agent outputs.

These schemas are the data contracts between agents.
Agent 1 must produce MARKET_MAP_SCHEMA.
Agent 2 must produce PROFILE_SCHEMA (array of these).
Agent 3 must produce CRITIQUE_SCHEMA.

Defining them explicitly here means:
  - Validation is automatic
  - Downstream agents know what to expect
  - Debugging is fast when an agent drifts
"""

# What Agent 1 (Market Mapper / Gemini) must return
MARKET_MAP_SCHEMA = {
    "type": "object",
    "required": ["target_companies", "talent_pools", "comp_range", "search_notes"],
    "properties": {
        "target_companies": {
            "type": "array",
            "description": "12-15 companies to target in this search",
            "items": {
                "type": "object",
                "required": ["name", "tier", "rationale", "suggested_titles"],
                "properties": {
                    "name":             {"type": "string"},
                    "tier":             {"type": "string", "enum": ["primary", "secondary", "stretch"]},
                    "rationale":        {"type": "string", "description": "1-sentence explanation of relevance"},
                    "suggested_titles": {"type": "array", "items": {"type": "string"}, "description": "2-3 titles to search within this company"}
                }
            }
        },
        "talent_pools": {
            "type": "array",
            "description": "3 talent clusters to draw from",
            "items": {
                "type": "object",
                "required": ["cluster_name", "description", "why_relevant"],
                "properties": {
                    "cluster_name": {"type": "string"},
                    "description":  {"type": "string"},
                    "why_relevant": {"type": "string"}
                }
            }
        },
        "comp_range":   {"type": "string", "description": "e.g. '$400k–$600k total comp'"},
        "search_notes": {"type": "string", "description": "2-3 sentences on where to prioritize effort"}
    }
}

# What each item in Agent 2's output (Profile Generator / GPT-4o) must look like
PROFILE_SCHEMA = {
    "type": "object",
    "required": [
        "profile_id", "name", "current_title", "current_company",
        "career_summary", "key_credentials", "why_they_fit", "questions_to_probe"
    ],
    "properties": {
        "profile_id":       {"type": "integer", "description": "1-indexed"},
        "name":             {"type": "string"},
        "current_title":    {"type": "string"},
        "current_company":  {"type": "string"},
        "career_summary":   {"type": "string", "description": "3-4 sentence trajectory narrative"},
        "key_credentials":  {"type": "array",  "items": {"type": "string"}, "description": "3-5 concrete credential points"},
        "why_they_fit":     {"type": "string", "description": "Specific argument for fit against this brief — not generic"},
        "questions_to_probe": {"type": "array", "items": {"type": "string"}, "description": "2-3 interview questions that probe the gaps"}
    }
}

# What Agent 3 (Profile Critic / Claude) must return
CRITIQUE_SCHEMA = {
    "type": "object",
    "required": ["critiques", "batch_summary"],
    "properties": {
        "critiques": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["profile_id", "confidence", "action", "issues", "strengths", "reviewer_note"],
                "properties": {
                    "profile_id":    {"type": "integer"},
                    "confidence":    {"type": "string", "enum": ["high", "medium", "low"]},
                    "action":        {"type": "string", "enum": ["keep", "revise", "drop"]},
                    "issues":        {"type": "array",  "items": {"type": "string"}},
                    "strengths":     {"type": "array",  "items": {"type": "string"}, "description": "max 2"},
                    "reviewer_note": {"type": "string", "description": "one sentence a human would write in a search tracker"}
                }
            }
        },
        "batch_summary": {
            "type": "object",
            "required": ["overall_quality", "top_3_profiles", "failure_pattern"],
            "properties": {
                "overall_quality":  {"type": "string", "enum": ["strong", "mixed", "weak"]},
                "top_3_profiles":   {"type": "array",  "items": {"type": "integer"}},
                "failure_pattern":  {"type": "string", "description": "most common issue pattern across the set"}
            }
        }
    }
}


def validate_json_structure(data: dict, required_keys: list, schema_name: str) -> list[str]:
    """
    Lightweight structural validator — checks that required top-level keys exist.
    Returns a list of error strings (empty = valid).
    Not a full JSON Schema validator — fast and dependency-free.
    """
    errors = []
    for key in required_keys:
        if key not in data:
            errors.append(f"[{schema_name}] Missing required key: '{key}'")
    return errors
