#!/usr/bin/env python3
"""
Stream Formatter — transforms raw AI agent output into clean,
structured events for the Shipcrawler dashboard.

Converts raw tool calls, thinking blocks, and JSON responses into
human-readable data points, status updates, and findings.
Strips all references to tool internals, prompts, plumbing, and noise.
"""

import re
from typing import Optional


# ── Patterns ──────────────────────────────────────────────────────────────

# New format: ┊ 🔍 search ... or ┊ 💻 terminal ...
EMOJI_TOOL_RE = re.compile(
    r"^┊\s*([\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF])\s+(\w+)"
)

# Legacy format: ● [Tool: name]
LEGACY_TOOL_RE = re.compile(r"●\s*\[Tool:\s*(\w+)\]")

# Legacy error: ● [Error: ...]
LEGACY_ERROR_RE = re.compile(r"●\s*\[Error:")

# Box-drawing thinking block lines (border chars)
BOX_BORDER_RE = re.compile(r"^[╭╰╰╮╯╌╍╎╏═─╌┄┈┅┉┅]")
BOX_CONTENT_RE = re.compile(r"^│")

# ── Prompt / noise patterns ──────────────────────────────────────────────

# The full prompt text that Hermes echoes at the start
PROMPT_KEYWORDS = [
    "Query: Using the shipcrawler",
    "Execute ALL phases",
    "Phase 0: Vessel Identity",
    "Phase 1: Target Identification",
    "Generate a COMPREHENSIVE",
    "CRITICAL: Write all report",
    "Be thorough — use multiple",
    "Research context:",
    "Identity & Academic Sources",
    "Research Impact Analysis",
    "Social & Digital Footprint",
    "Professional Network & Timeline",
    "Targeting Scenarios",
    "analyst-report.md (full",
    "red-team-playbook.md (2-3",
    "indicators-and-detection.md",
    "Elastic rules, Zeek scripts",
    "1. analyst-report.md",
    "2. red-team-playbook.md",
    "3. indicators-and-detection.md",
    "confidence assessment per category",
    "vault/osint-reports",
    "<name>-report",
    # Fragments from the name in quotes in prompt
    '\\"Nasr',
    '\\"',
]

TOOL_PREPARE_RE = re.compile(r"┊\s*.\s*preparing\s+\w+")

# ── Data extraction patterns ─────────────────────────────────────────────

# Shodan findings
PORT_FOUND_RE = re.compile(r"(\d+)\s*(open\s*)?ports?\s*found", re.IGNORECASE)
SERVICE_FOUND_RE = re.compile(
    r"(Port\s*\d+|SSH|HTTP|HTTPS|FTP|Telnet|SNMP|NMEA|Signal\s*K|VSAT|ECDIS|MODBUS|AIS)\s*[:‑]?\s*(\w+)",
    re.IGNORECASE,
)

# Risk / findings
FINDING_RE = re.compile(
    r"(HIGH|MEDIUM|LOW|CRITICAL)\s*(risk|severity|confidence|exposure)",
    re.IGNORECASE,
)

# CVE
CVE_RE = re.compile(r"(CVE-\d{4}-\d{4,7})", re.IGNORECASE)

# File written / saved
FILE_SAVED_RE = re.compile(r"w(?:as\s+)?(?:written|saved|created)\s*(?:to\s*)?[:\s]*(.+\.md)", re.IGNORECASE)
FILE_EMOJI_RE = re.compile(r"💾\s*(.+\.md)", re.IGNORECASE)

# IP addresses
IP_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?)\b")

# Coordinates
COORDS_RE = re.compile(r"(\d+\.\d+[°'\"NSEW]?\s*,?\s*\d+\.\d+[°'\"NSEW]?)")

# Critical finding marker
CRITICAL_FINDING_RE = re.compile(r"(CRITICAL FINDING|Key Finding|Important)")

# ── Helpers ──────────────────────────────────────────────────────────────


def _is_prompt_line(stripped: str) -> bool:
    """Return True if the line is part of the echoed prompt."""
    for kw in PROMPT_KEYWORDS:
        if kw in stripped:
            return True
    return False


def _strip_hermes_refs(text: str) -> str:
    text = re.sub(r"(?i)\bhermes\b", "agent", text)
    return text


def _is_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    # Pure separators
    if re.match(r"^[\─\━\═\╌\┅\┄\┉\┈\-\=\_]{3,}$", stripped):
        return True
    # Prompt echoes
    if _is_prompt_line(stripped):
        return True
    # Tool preparation noise
    if TOOL_PREPARE_RE.match(stripped):
        return True
    # "Initializing agent..." and similar
    if re.match(r"^(Initializing|Setting up|Loading|Starting|Preparing)", stripped, re.IGNORECASE):
        return True
    # Raw $ commands
    if re.match(r"^\$\s", stripped):
        return True
    # Internal tool plumbing
    if re.match(r"^(sudo |curl |pip |git |cd |apt |npm |yarn |docker |make |rm |cp |mv |chmod |equasis )", stripped):
        return True
    # Raw $ commands (terminal commands shown literally)
    if "$ " in stripped or stripped.startswith("$"):
        return True
    # Raw JSON
    if stripped.startswith("{") or stripped.startswith("["):
        return True
    # Box borders
    if BOX_BORDER_RE.match(stripped):
        return True
    # Env/setup
    if stripped.startswith("export ") or stripped.startswith("source "):
        return True
    return False


def _classify_line(line: str) -> Optional[dict]:
    stripped = line.strip().rstrip("│")
    stripped = stripped.strip()
    is_indented = line.startswith("  ") or line.startswith("\t")

    if not stripped:
        return None
    if _is_noise(stripped):
        return None

    text = _strip_hermes_refs(stripped)
    text_lower = text.lower()

    # ── Tool start lines: convert to clean status ──────────────
    match = EMOJI_TOOL_RE.match(stripped)
    if match:
        emoji = match.group(1)
        tool = match.group(2).lower()
        return _tool_to_status(emoji, tool, text)

    if LEGACY_TOOL_RE.match(stripped):
        tool_match = LEGACY_TOOL_RE.match(stripped)
        tool = tool_match.group(1).lower() if tool_match else "tool"
        return _tool_to_status_legacy(tool, text)

    # ── Error lines ───────────────────────────────────────────
    if LEGACY_ERROR_RE.match(stripped):
        return {"type": "error", "icon": "❌", "message": text[:200]}

    # ── Box content lines: │ content here → clean status ─────
    if BOX_CONTENT_RE.match(line):
        content = re.sub(r"^│\s*", "", stripped)
        content = _strip_hermes_refs(content).strip()
        # If it has a critical finding marker, highlight it
        if CRITICAL_FINDING_RE.search(content):
            clean_message = re.sub(r"(?i)CRITICAL FINDING:\s*", "", content).strip()
            return {"type": "finding", "icon": "🔍", "message": f"Found: {clean_message}"[:250]}
        if content:
            return {"type": "status", "icon": "  ", "message": content[:250]}
        return None

    # ── Data extraction patterns ──────────────────────────────
    # Shodan port findings
    port_match = PORT_FOUND_RE.search(text)
    if port_match:
        count = port_match.group(1)
        return {
            "type": "data_point", "icon": "📡",
            "message": f"{count} open port{'s' if count != '1' else ''} found on network scan",
        }

    # Risk / severity findings
    risk_match = FINDING_RE.search(text)
    if risk_match:
        severity = risk_match.group(1).upper()
        icons = {"CRITICAL": "🔥", "HIGH": "⚠️", "MEDIUM": "⚡", "LOW": "ℹ️"}
        icon = icons.get(severity, "📋")
        return {"type": "finding", "icon": icon, "message": text[:250]}

    # CVE
    if CVE_RE.search(text):
        return {"type": "finding", "icon": "🔓", "message": text[:250]}

    # Critical finding marker
    if CRITICAL_FINDING_RE.search(text):
        return {"type": "finding", "icon": "🔍", "message": text[:250]}

    # File saved
    file_match = FILE_SAVED_RE.search(text) or FILE_EMOJI_RE.search(text)
    if file_match:
        return {"type": "complete", "icon": "💾", "message": f"Report saved: {file_match.group(1).strip()}"}

    # IP addresses
    ip_match = IP_RE.search(text)
    if ip_match:
        return {"type": "data_point", "icon": "🌐", "message": text[:250]}

    # Port/service data
    if SERVICE_FOUND_RE.search(text):
        return {"type": "data_point", "icon": "🔌", "message": text[:250]}

    # Coordinates
    if COORDS_RE.search(text):
        return {"type": "data_point", "icon": "📍", "message": text[:200]}

    # ── Indented detail lines ─────────────────────────────────
    if is_indented:
        detail = text.strip()
        has_data_marker = (
            ":" in detail
            or re.match(r"^[\d\-–—•*▶]", detail.strip())
            or any(k in text_lower for k in ["port", "flag", "imo", "mmsi", "risk", "cve", "email", "domain", "ip", "built", "type", "status", "speed", "destination"])
        )
        if has_data_marker:
            return {"type": "data_point", "icon": "  →", "message": detail[:250]}
        return {"type": "status", "icon": "  ", "message": detail[:250]}

    # ── Default: clean status ──────────────────────────────────
    known_prefixes = {"✅", "❌", "📋", "📡", "⚠️", "🔍", "🔓", "💾", "📍", "🌐", "🔌", "🧠"}
    first_char = text[0] if text else ""
    if first_char in known_prefixes:
        icon = first_char
        msg = text[1:].strip()
    else:
        icon = "  "
        msg = text

    return {"type": "status", "icon": icon, "message": msg[:300]}


def _strip_timing(text: str) -> str:
    """Strip trailing timing/duration metadata from tool output lines."""
    return re.sub(r"\s+\+?\d+(\.\d+)?[smhd]?\s*$", "", text).strip()


def _tool_to_status(emoji: str, tool: str, original: str) -> Optional[dict]:
    """Map emoji + tool name to clean status message. Returns None to suppress."""
    text = _strip_hermes_refs(original)

    # Strip the ┊ emoji tool prefix
    clean_text = re.sub(r"^┊\s*.\s*\w+\s*", "", text).strip()

    # Suppress tool preparation lines
    if tool == "preparing":
        return None

    # Suppress raw $ commands (e.g. "$ equasis configure --setup")
    if clean_text.startswith("$"):
        return None

    tool_map = {
        "search": ("🔍", None),
        "extract": ("📄", None),
        "exec": ("🐍", None),
        "terminal": ("💻", None),
        "bash": ("💻", None),
        "fetch": ("📄", None),
    }

    icon, _ = tool_map.get(tool, (None, None))

    if icon:
        # Use the clean text that follows the tool prefix
        msg = clean_text if clean_text else f"Running {tool}..."
        msg = _strip_timing(msg)
        return {"type": "status", "icon": icon, "message": msg[:250]}

    # Unknown tool — suppress unless there's meaningful text
    clean_text = _strip_timing(clean_text)
    if clean_text and len(clean_text) > 3:
        return {"type": "status", "icon": "  ", "message": clean_text[:250]}
    return None


def _tool_to_status_legacy(tool: str, original: str) -> dict:
    text = _strip_hermes_refs(original)
    clean_text = re.sub(r"●\s*\[Tool:\s*\w+\]\s*", "", text).strip()
    return {"type": "status", "icon": "⏳", "message": clean_text[:250]}


def process_output_line(line: str) -> Optional[dict]:
    """
    Public API: process one line of raw output.

    Returns a structured event dict with keys:
      - type: "status" | "data_point" | "finding" | "warning" | "error" | "complete"
      - icon: str (emoji or indent)
      - message: str (cleaned text)

    Returns None if the line should be suppressed.
    """
    return _classify_line(line)
