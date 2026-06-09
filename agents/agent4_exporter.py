"""
SearchIQ — Agent 4: Google Sheets Exporter

Takes the merged pipeline output (profiles + critiques) and writes
two formatted tabs to a Google Sheet:
  Tab 1 "All Profiles"  — all 10 rows with full data + critique scores
  Tab 2 "Flagged"       — only profiles where action = revise or drop

Setup (one-time):
  1. Go to console.cloud.google.com → APIs → Enable Google Sheets API
  2. Create a Service Account → download JSON credentials
  3. Share your target Google Sheet with the service account email
  4. Set GOOGLE_SHEETS_CREDS_PATH and GOOGLE_SHEET_ID in .env

If Google Sheets is not configured, this agent falls back to writing
a local CSV — the pipeline always completes regardless.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import csv
import json
import time
from utils import get_logger, RunMetadata

logger = get_logger("Agent4.Exporter")

# Column headers for the export sheet
HEADERS = [
    "Profile ID", "Name", "Current Title", "Current Company",
    "Career Summary", "Key Credentials", "Why They Fit", "Questions to Probe",
    "Confidence", "Action", "Issues", "Strengths", "Reviewer Note"
]

CONFIDENCE_COLORS = {
    "high":   (0.85, 0.94, 0.83),   # light green
    "medium": (1.00, 0.95, 0.80),   # light amber
    "low":    (0.96, 0.80, 0.80),   # light red
}

ACTION_COLORS = {
    "keep":   (0.85, 0.94, 0.83),
    "revise": (1.00, 0.95, 0.80),
    "drop":   (0.96, 0.80, 0.80),
}


def _merge_row(profile: dict, critique: dict | None) -> list:
    """Merges one profile + its critique into a flat list for sheet row."""
    crit = critique or {}
    return [
        profile.get("profile_id", ""),
        profile.get("name", ""),
        profile.get("current_title", ""),
        profile.get("current_company", ""),
        profile.get("career_summary", ""),
        " | ".join(profile.get("key_credentials", [])),
        profile.get("why_they_fit", ""),
        " | ".join(profile.get("questions_to_probe", [])),
        crit.get("confidence", ""),
        crit.get("action", ""),
        " | ".join(crit.get("issues", [])),
        " | ".join(crit.get("strengths", [])),
        crit.get("reviewer_note", ""),
    ]


def _build_critique_map(critique: dict) -> dict:
    """Returns {profile_id: critique_dict} for O(1) lookup."""
    return {c["profile_id"]: c for c in critique.get("critiques", [])}


class SheetsExporter:

    def __init__(self, creds_path: str | None = None, sheet_id: str | None = None):
        self.creds_path = creds_path or os.getenv("GOOGLE_SHEETS_CREDS_PATH", "")
        self.sheet_id   = sheet_id   or os.getenv("GOOGLE_SHEET_ID", "")
        self._sheets    = None   # lazy init

    def _init_sheets(self) -> bool:
        """Returns True if Sheets client initialised successfully."""
        if self._sheets:
            return True
        if not self.creds_path or not self.sheet_id:
            logger.info("Google Sheets not configured — will write CSV instead")
            return False
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds        = Credentials.from_service_account_file(self.creds_path, scopes=scopes)
            self._gc     = gspread.authorize(creds)
            self._sheets = self._gc.open_by_key(self.sheet_id)
            logger.info(f"Google Sheets connected | sheet_id={self.sheet_id[:12]}...")
            return True
        except Exception as e:
            logger.warning(f"Google Sheets init failed: {e} — falling back to CSV")
            return False

    def _get_or_create_tab(self, title: str, cols: int, rows: int):
        """Returns a worksheet, creating it if it doesn't exist."""
        try:
            ws = self._sheets.worksheet(title)
            ws.clear()
            return ws
        except Exception:
            return self._sheets.add_worksheet(title=title, rows=rows, cols=cols)

    def _write_to_sheets(self, all_rows: list, flagged_rows: list,
                          batch_summary: dict) -> str:
        """Writes to Google Sheets. Returns the sheet URL."""
        # Tab 1 — All Profiles
        ws_all = self._get_or_create_tab("All Profiles", cols=len(HEADERS), rows=50)
        ws_all.update([HEADERS] + all_rows)
        self._format_header(ws_all)
        self._format_confidence_column(ws_all, all_rows)

        # Tab 2 — Flagged for Review
        ws_flag = self._get_or_create_tab("Flagged for Review", cols=len(HEADERS), rows=30)
        if flagged_rows:
            ws_flag.update([HEADERS] + flagged_rows)
            self._format_header(ws_flag)
            self._format_confidence_column(ws_flag, flagged_rows)
        else:
            ws_flag.update([["No profiles flagged for review — all rated 'keep'"]])

        # Tab 3 — Batch Summary
        ws_sum = self._get_or_create_tab("Batch Summary", cols=2, rows=10)
        summary_rows = [
            ["Field", "Value"],
            ["Overall quality",  batch_summary.get("overall_quality", "")],
            ["Top 3 profiles",   str(batch_summary.get("top_3_profiles", []))],
            ["Failure pattern",  batch_summary.get("failure_pattern", "")],
            ["Total profiles",   str(len(all_rows))],
            ["Flagged count",    str(len(flagged_rows))],
            ["Generated at",     time.strftime("%Y-%m-%d %H:%M")],
        ]
        ws_sum.update(summary_rows)
        self._format_header(ws_sum)

        url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
        logger.info(f"Google Sheet written | {url}")
        return url

    def _format_header(self, ws):
        """Bolds the header row and freezes it."""
        try:
            import gspread.utils
            ws.format("1:1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.23, "green": 0.33, "blue": 0.53}
            })
            ws.freeze(rows=1)
        except Exception:
            pass   # formatting is best-effort

    def _format_confidence_column(self, ws, data_rows: list):
        """Color-codes the Confidence column (column I = index 9)."""
        try:
            for i, row in enumerate(data_rows, start=2):
                confidence = row[8] if len(row) > 8 else ""
                color      = CONFIDENCE_COLORS.get(confidence)
                if color:
                    r, g, b = color
                    ws.format(f"I{i}", {"backgroundColor": {"red": r, "green": g, "blue": b}})
                    ws.format(f"J{i}", {"backgroundColor": {"red": r, "green": g, "blue": b}})
        except Exception:
            pass   # formatting is best-effort

    def _write_csv(self, all_rows: list, flagged_rows: list,
                   batch_summary: dict) -> str:
        """CSV fallback when Sheets is not configured."""
        Path("outputs").mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")

        # All profiles
        all_path = Path(f"outputs/searchiq_all_profiles_{ts}.csv")
        with open(all_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADERS)
            w.writerows(all_rows)

        # Flagged
        flag_path = Path(f"outputs/searchiq_flagged_{ts}.csv")
        with open(flag_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADERS)
            w.writerows(flagged_rows if flagged_rows else [["No flagged profiles"]])

        # Summary
        sum_path = Path(f"outputs/searchiq_summary_{ts}.json")
        with open(sum_path, "w") as f:
            json.dump(batch_summary, f, indent=2)

        logger.info(f"CSV files written -> {all_path.name}, {flag_path.name}")
        return str(all_path)

    def run(self, profiles: list, critique: dict,
            metadata: RunMetadata | None = None) -> dict:
        """
        Main entry point.
        Returns {"destination": "sheets"|"csv", "url_or_path": str,
                 "total_rows": int, "flagged_rows": int}
        """
        logger.info("Building export rows...")
        start        = time.time()
        crit_map     = _build_critique_map(critique)
        batch_sum    = critique.get("batch_summary", {})

        all_rows     = [_merge_row(p, crit_map.get(p["profile_id"])) for p in profiles]
        flagged_rows = [r for r in all_rows if r[9] in ("revise", "drop")]

        logger.info(f"Export: {len(all_rows)} total | {len(flagged_rows)} flagged")

        use_sheets = self._init_sheets()
        if use_sheets:
            try:
                url = self._write_to_sheets(all_rows, flagged_rows, batch_sum)
                dest = "sheets"
            except Exception as e:
                logger.warning(f"Sheets write failed: {e} — falling back to CSV")
                url  = self._write_csv(all_rows, flagged_rows, batch_sum)
                dest = "csv"
        else:
            url  = self._write_csv(all_rows, flagged_rows, batch_sum)
            dest = "csv"

        duration = round(time.time() - start, 2)
        if metadata:
            metadata.record("Agent4.Exporter", "ok", duration)

        return {
            "destination":  dest,
            "url_or_path":  url,
            "total_rows":   len(all_rows),
            "flagged_rows": len(flagged_rows),
        }
