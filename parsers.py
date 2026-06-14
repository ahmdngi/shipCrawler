#!/usr/bin/env python3
"""
Markdown Report Parser — extracts structured card data from raw Hermes markdown output.
Works with both vessel and person OSINT report formats.
"""

import re
from typing import Any


def parse_into_sections(text: str) -> dict[str, str]:
    """Split markdown text into ## and ### heading-anchored sections."""
    sections = {}
    current_heading = None
    current_lines = []

    for line in text.split("\n"):
        stripped = line.rstrip()
        if stripped.startswith("### ") or stripped.startswith("## "):
            # Collapse multiple hashes
            heading = re.sub(r"^#+\s+", "", stripped).strip()
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = heading
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def extract_key_value_table(text: str) -> dict[str, str]:
    """Extract key-value pairs from a markdown table where first col = key, second col = value.
    
    Handles:
    | **Name** | MEGASTAR |
    | Name | MEGASTAR |
    """
    pairs = {}
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) >= 2:
            # Check it's not a header/separator
            if all(c.startswith("-") or c.startswith(":") for c in cells):
                continue
            key = re.sub(r"\*\*", "", cells[0]).strip()
            val = re.sub(r"\*\*", "", cells[1]).strip()
            if key and val and key.lower() not in ("field", "attribute", "detail", "metric", "category", "confidence"):
                pairs[key] = val
    return pairs


def extract_multi_column_table(text: str) -> list[dict[str, str]]:
    """Extract a markdown table with multiple columns as list of dicts."""
    rows = []
    headers = []
    in_table = False

    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            in_table = False
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]

        if not cells:
            continue

        # Skip separator rows
        if all(c.startswith("-") or c.startswith(":") for c in cells):
            continue

        if not headers:
            # Clean header names
            headers = [re.sub(r"\*\*", "", c).strip().lower().replace(" ", "_") for c in cells]
            in_table = True
        else:
            # Data row
            row = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    row[headers[i]] = re.sub(r"\*\*", "", cell).strip()
            rows.append(row)
            in_table = True

    return rows


def extract_vessel_fields(sections: dict[str, str]) -> dict[str, Any]:
    """Extract vessel OSINT structured data from parsed sections."""
    result = {}

    # --- Vessel Identity ---
    for sec_name in sections:
        if "vessel identity" in sec_name.lower():
            kv = extract_key_value_table(sections[sec_name])
            if kv:
                result["vessel_identity"] = kv
                break

    # --- Current Status ---
    for sec_name in sections:
        if "current status" in sec_name.lower():
            kv = extract_key_value_table(sections[sec_name])
            if kv:
                result["current_status"] = {}
                for k, v in kv.items():
                    kl = k.lower()
                    if "position" in kl:
                        result["current_status"]["Position"] = v
                    elif "status" in kl and "navigation" in kl:
                        result["current_status"]["Status"] = v
                    elif "speed" in kl:
                        result["current_status"]["Speed"] = v
                    elif "course" in kl:
                        result["current_status"]["Course"] = v
                    elif "destination" in kl:
                        result["current_status"]["Destination"] = v
                    elif "eta" in kl:
                        result["current_status"]["ETA"] = v
                    elif "draught" in kl:
                        result["current_status"]["Draught"] = v
                break

    # --- Port Calls ---
    for sec_name in sections:
        if "port call" in sec_name.lower():
            tables = extract_multi_column_table(sections[sec_name])
            if tables:
                result["port_calls"] = tables
            break

    # --- Shodan ---
    for sec_name in sections:
        if "shodan" in sec_name.lower():
            text = sections[sec_name]
            summary_parts = []
            for line in text.split("\n"):
                line = line.strip()
                if line and not line.startswith("|") and not line.startswith("---"):
                    summary_parts.append(line)
            result["shodan"] = {
                "summary": " ".join(summary_parts)[:300],
                "results": [],
            }
            break

    # --- Confidence Assessment ---
    for sec_name in sections:
        if "confidence" in sec_name.lower():
            kv = extract_key_value_table(sections[sec_name])
            categories = {}
            overall = "MEDIUM"
            for k, v in kv.items():
                val_upper = v.upper()
                if val_upper in ("HIGH", "MEDIUM", "LOW", "SPECULATIVE"):
                    categories[k] = val_upper
            if categories:
                overall = max(set(categories.values()), key=list(categories.values()).count)
            result["confidence_assessment"] = {
                "overall": overall,
                "categories": categories,
            }
            break

    # --- Analysis ---
    risk_tier = "LOW"
    text_all = "\n".join(sections.values())
    risk_match = re.search(r"risk\s+tier[:\s]+(\w+)", text_all, re.IGNORECASE)
    if risk_match:
        risk_tier = risk_match.group(1).upper()
    result["analysis"] = {"risk_tier": risk_tier, "notes": ["Report generated by Hermes agent"]}

    # --- Red Team Playbook (if present) ---
    vectors = []
    for sec_name in sections:
        if "vector" in sec_name.lower() and ":" in sec_name:
            vectors.append({
                "name": sec_name,
                "difficulty": "MEDIUM",
                "cost": "",
                "detection_prob": "MEDIUM",
                "steps": [],
                "detection_points": [],
            })
    if vectors:
        result["red_team_playbook"] = {"vectors": vectors}

    return result


def extract_person_fields(sections: dict[str, str]) -> dict[str, Any]:
    """Extract person OSINT structured data from parsed sections."""
    result = {}

    # --- Person Identity ---
    for sec_name in sections:
        if "identity" in sec_name.lower() and "vessel" not in sec_name.lower():
            kv = extract_key_value_table(sections[sec_name])
            if kv:
                result["person_identity"] = kv
                break

    # --- Professional History ---
    for sec_name in sections:
        if any(w in sec_name.lower() for w in ["professional", "position", "career", "employment", "affiliation"]):
            tables = extract_multi_column_table(sections[sec_name])
            if tables:
                result["professional_history"] = []
                for row in tables:
                    result["professional_history"].append({
                        "role": row.get("role", row.get("position", "")),
                        "company": row.get("company", row.get("institution", row.get("organization", ""))),
                        "period": row.get("period", row.get("year", row.get("start_date", ""))),
                    })
            break

    # --- Education ---
    for sec_name in sections:
        if "education" in sec_name.lower():
            edu_lines = []
            for line in sections[sec_name].split("\n"):
                line = line.strip()
                if line.startswith("-") or line.startswith("*"):
                    edu_lines.append(line.lstrip("-* ").strip())
                elif line.startswith("|"):
                    # Try table
                    cells = [c.strip() for c in line.split("|")[1:-1]]
                    if len(cells) >= 2:
                        edu_lines.append(" | ".join(cells))
            if edu_lines:
                result["education"] = edu_lines
            break

    # --- Research Impact ---
    for sec_name in sections:
        if any(w in sec_name.lower() for w in ["research", "citation", "impact", "h-index", "publication"]):
            kv = extract_key_value_table(sections[sec_name])
            impact = {}
            if kv:
                for k, v in kv.items():
                    kl = k.lower()
                    if "publication" in kl and "total" in kl:
                        try:
                            impact["total_publications"] = int(re.sub(r"[^\d]", "", v))
                        except ValueError:
                            impact["total_publications"] = 0
                    elif "citation" in kl and "total" in kl:
                        try:
                            impact["total_citations"] = int(re.sub(r"[^\d]", "", v))
                        except ValueError:
                            impact["total_citations"] = 0
                    elif "h-index" in kl or "h_index" in kl:
                        try:
                            impact["h_index"] = int(re.sub(r"[^\d]", "", v))
                        except ValueError:
                            impact["h_index"] = 0
                    elif "i10" in kl:
                        try:
                            impact["i10_index"] = int(re.sub(r"[^\d]", "", v))
                        except ValueError:
                            impact["i10_index"] = 0
                if impact:
                    result["research_impact"] = impact
            break

    # --- Social Media / Digital Footprint ---
    footprint = []
    for sec_name in sections:
        if any(w in sec_name.lower() for w in ["social", "digital", "footprint", "online"]):
            for line in sections[sec_name].split("\n"):
                # Look for URLs
                urls = re.findall(r"https?://[^\s,)]+", line)
                if urls:
                    platform = ""
                    for p in ["LinkedIn", "GitHub", "Twitter", "X.com", "Google Scholar",
                               "ORCID", "ResearchGate", "Facebook", "Instagram"]:
                        if p.lower() in line.lower():
                            platform = p
                            break
                    if not platform:
                        platform = urls[0].split("//")[1].split("/")[0]
                    footprint.append({"source": platform, "detail": urls[0]})
            break
    if footprint:
        result["digital_footprint"] = footprint

    # --- Confidence ---
    for sec_name in sections:
        if "confidence" in sec_name.lower():
            kv = extract_key_value_table(sections[sec_name])
            categories = {}
            overall = "MEDIUM"
            for k, v in kv.items():
                val_upper = v.upper()
                if val_upper in ("HIGH", "MEDIUM", "LOW", "SPECULATIVE"):
                    categories[k] = val_upper
            if categories:
                overall = max(set(categories.values()), key=list(categories.values()).count)
            result["confidence_assessment"] = {
                "overall": overall,
                "categories": categories,
            }
            break

    # --- Targeting Scenarios ---
    vectors = []
    for sec_name in sections:
        if "vector" in sec_name.lower() and ":" in sec_name:
            vectors.append({
                "name": sec_name,
                "difficulty": "MEDIUM",
                "cost": "",
                "detection_prob": "MEDIUM",
                "steps": [],
                "detection_points": [],
            })
    if vectors:
        result["targeting_scenarios"] = {"vectors": vectors, "summary": f"{len(vectors)} attack vectors from OSINT analysis"}

    return result


def parse_report(raw_text: str, mode: str = "vessel") -> dict[str, Any]:
    """
    Main entry point. Takes raw markdown text from Hermes output
    and returns structured JSON for the dashboard frontend cards.
    """
    if not raw_text:
        return {"error": "No report content"}

    sections = parse_into_sections(raw_text)

    if mode == "person":
        parsed = extract_person_fields(sections)
    else:
        parsed = extract_vessel_fields(sections)

    parsed["mode"] = mode
    return parsed
