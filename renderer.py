#!/usr/bin/env python3
"""
Markdown Report Renderer — reads shipcrawler report markdown files and
converts them into structured JSON for the dashboard frontend cards.
"""

import json
import os
import re
from pathlib import Path


def parse_section_blocks(text):
    """Split markdown text into heading-anchored sections."""
    sections = {}
    current_heading = None
    current_lines = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            continue  # skip document title
        else:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def parse_table_row(line):
    """Parse a markdown table row into cells."""
    cells = []
    for cell in line.split("|"):
        cell = cell.strip()
        if cell and not cell.startswith("-") and not cell.startswith(":"):
            cells.append(cell)
    return cells


def extract_tables(text):
    """Extract tables from markdown text. Returns list of dicts with headers + rows."""
    tables = []
    lines = text.split("\n")
    in_table = False
    headers = []
    rows = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if not cells:
                continue
            if not in_table:
                in_table = True
                # Check if next line is separator
                continue
            elif headers and all(c.startswith("-") or c.startswith(":") for c in cells):
                continue  # separator line
            elif not headers:
                headers = cells
            else:
                rows.append(dict(zip(headers, cells)))
        else:
            if in_table and rows:
                tables.append({"headers": headers, "rows": rows})
                headers = []
                rows = []
            in_table = False

    if in_table and rows:
        tables.append({"headers": headers, "rows": rows})

    return tables


def render_person_report(report_dir):
    """Read the 5 person OSINT markdown files and return card-ready JSON."""
    report_dir = Path(report_dir)
    cards = {}

    # ── README.md ────────────────────────────────────────────────
    readme_path = report_dir / "README.md"
    if readme_path.exists():
        text = readme_path.read_text()
        cards["summary"] = {"key_finding": "", "confidence": ""}
        for line in text.split("\n"):
            if line.startswith("## Key Finding"):
                continue
            if line.strip() and not line.startswith("#") and not line.startswith("---"):
                cards["summary"]["key_finding"] = line.strip()
                break

    # ── analyst-report.md ────────────────────────────────────────
    analyst_path = report_dir / "analyst-report.md"
    if analyst_path.exists():
        text = analyst_path.read_text()
        sections = parse_section_blocks(text)

        # Section 1: Identity
        identity = {}
        if "1. Identity" in sections:
            for line in sections["1. Identity"].split("\n"):
                m = re.match(r"\| ([^|]+) \| ([^|]+) \|", line)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    if val not in ("HIGH", "MEDIUM", "LOW"):
                        identity[key] = val
        cards["person_identity"] = identity

        # Section 2: Current Positions
        positions = []
        if "2. Current Positions" in sections:
            tables = extract_tables(sections["2. Current Positions"])
            if tables:
                for row in tables[0]["rows"]:
                    positions.append({
                        "role": row.get("Role", ""),
                        "institution": row.get("Institution", "") or row.get("Department", ""),
                        "period": row.get("Start Date", ""),
                    })
        cards["professional_history"] = positions

        # Section 3: Education
        education = []
        if "3. Education" in sections:
            tables = extract_tables(sections["3. Education"])
            if tables:
                for row in tables[0]["rows"]:
                    education.append(f"{row.get('Degree', '')} at {row.get('Institution', '')} ({row.get('Year', '')})")
        cards["education"] = education

        # Section 9: Digital Footprint
        footprint = []
        if "9. Digital Footprint" in sections:
            tables = extract_tables(sections["9. Digital Footprint"])
            if tables:
                for row in tables[0]["rows"]:
                    footprint.append({
                        "source": row.get("Platform", ""),
                        "detail": row.get("URL / Handle", "") or row.get("Activity Type", ""),
                    })
        cards["digital_footprint"] = footprint

        # Section 13: Confidence
        confidence = {}
        if "13. Confidence Assessment" in sections:
            tables = extract_tables(sections["13. Confidence Assessment"])
            if tables:
                for row in tables[0]["rows"]:
                    cat = row.get("Category", "")
                    val = row.get("Confidence", "")
                    if cat and val:
                        confidence[cat] = val
        cards["confidence_assessment"] = {
            "overall": max(set(confidence.values()), key=list(confidence.values()).count) if confidence else "MEDIUM",
            "categories": confidence,
        }

    # ── research-impact-analysis.md ──────────────────────────────
    impact_path = report_dir / "research-impact-analysis.md"
    if impact_path.exists():
        text = impact_path.read_text()
        sections = parse_section_blocks(text)

        impact = {}
        if "1. Citation Metrics" in sections:
            tables = extract_tables(sections["1. Citation Metrics"])
            if tables:
                for row in tables[0]["rows"]:
                    key = row.get("Metric", "").lower().replace(" ", "_")
                    val = row.get("Value", "0")
                    try:
                        val = int(val.replace(",", ""))
                    except ValueError:
                        pass
                    impact[key] = val
        cards["research_impact"] = impact

        # Top publications
        top_pubs = []
        if "2. Top-5 Most Cited Publications" in sections:
            tables = extract_tables(sections["2. Top-5 Most Cited Publications"])
            if tables:
                for row in tables[0]["rows"]:
                    top_pubs.append({
                        "title": row.get("Title", ""),
                        "citations": int(row.get("Citations", "0")),
                        "year": row.get("Year", ""),
                    })
        if top_pubs:
            if "research_impact" not in cards:
                cards["research_impact"] = {}
            cards["research_impact"]["top_publications"] = top_pubs

        # Publication by year
        if "3. Publication Output by Year" in sections:
            tables = extract_tables(sections["3. Publication Output by Year"])
            if tables:
                by_year = {}
                for row in tables[0]["rows"]:
                    yr = row.get("Year", "")
                    papers = row.get("Papers", "0")
                    try:
                        by_year[yr] = int(papers)
                    except ValueError:
                        pass
                if by_year:
                    if "research_impact" not in cards:
                        cards["research_impact"] = {}
                    cards["research_impact"]["publications_by_year"] = by_year

        # Collaboration network
        if "5. Collaboration Network Analysis" in sections:
            coauthors = []
            tables = extract_tables(sections["5. Collaboration Network Analysis"])
            for t in tables:
                for row in t["rows"]:
                    coauthors.append({
                        "name": row.get("Co-author", "") or row.get("Country", ""),
                        "shared_papers": int(row.get("Shared Papers (est.)", "1")),
                    })
            if coauthors:
                cards["coauthors"] = coauthors

    # ── affiliation-timeline.md ──────────────────────────────────
    timeline_path = report_dir / "affiliation-timeline.md"
    if timeline_path.exists():
        text = timeline_path.read_text()
        sections = parse_section_blocks(text)

        timeline = {"current_positions": [], "past_positions": [], "education": []}

        if "3. Key Career Transitions" in sections:
            tables = extract_tables(sections["3. Key Career Transitions"])
            if tables:
                for row in tables[0]["rows"]:
                    timeline["past_positions"].append({
                        "role": row.get("Transition", ""),
                        "company": "",
                        "period": row.get("Year", ""),
                    })

        if "2. Geographic Mobility" in sections:
            tables = extract_tables(sections["2. Geographic Mobility"])
            if tables:
                locations = set()
                for row in tables[0]["rows"]:
                    loc = row.get("Location", "")
                    if "Estonia" in loc:
                        locations.add("Estonia")
                    if "Norway" in loc:
                        locations.add("Norway")
                    if "Germany" in loc:
                        locations.add("Germany")
                timeline["geographic_summary"] = ", ".join(sorted(locations))

        cards["affiliation_timeline"] = timeline

    # ── targeting-scenarios.md ───────────────────────────────────
    scenarios_path = report_dir / "targeting-scenarios.md"
    if scenarios_path.exists():
        text = scenarios_path.read_text()
        sections = parse_section_blocks(text)

        vectors = []
        for heading, content in sections.items():
            m = re.match(r"Vector ([A-Z]+): (.+)", heading)
            if m:
                vec = {
                    "name": f"{m.group(1)}: {m.group(2)}",
                    "difficulty": "MEDIUM",
                    "cost": "",
                    "detection_prob": "MEDIUM",
                    "steps": [],
                    "detection_points": [],
                }
                # Extract difficulty/cost/detection
                for line in content.split("\n"):
                    l = line.lower()
                    if "difficulty:" in l:
                        vec["difficulty"] = line.split("**")[1] if "**" in line else line.split(":")[-1].strip()
                    if "cost:" in l:
                        vec["cost"] = line.split("**")[1] if "**" in line else line.split(":")[-1].strip()
                    if "detection" in l and ":" in l:
                        vec["detection_prob"] = line.split("**")[1] if "**" in line else line.split(":")[-1].strip()

                # Extract equipment (bullet list)
                equipment = []
                for line in content.split("\n"):
                    if line.strip().startswith("-") or line.strip().startswith("*"):
                        item = line.strip().lstrip("-* ").strip()
                        if item and len(item) > 5 and not item.startswith("|"):
                            equipment.append(item)
                if equipment:
                    vec["equipment"] = equipment

                # Extract execution steps (numbered)
                for line in content.split("\n"):
                    m_step = re.match(r"\d+\.\s+(.+)", line.strip())
                    if m_step:
                        vec["steps"].append(m_step.group(1))

                # Extract detection point tables
                tables = extract_tables(content)
                for t in tables:
                    if "Detection Point" in str(t["headers"]) or "Point" in str(t["headers"]):
                        for row in t["rows"]:
                            vec["detection_points"].append({
                                "point": row.get("Detection Point", "") or row.get("Point", ""),
                                "signal": row.get("Expected Signal", "") or row.get("Signal", ""),
                                "tool": row.get("Tool", ""),
                            })

                vectors.append(vec)

        cards["targeting_scenarios"] = {
            "vectors": vectors,
            "summary": f"{len(vectors)} attack vectors from OSINT analysis",
        }

    return cards


def render_vessel_report(report_dir):
    """Read the 3 vessel OSINT markdown files and return card-ready JSON."""
    report_dir = Path(report_dir)
    cards = {}

    analyst_path = report_dir / "analyst-report.md"
    if analyst_path.exists():
        text = analyst_path.read_text()
        sections = parse_section_blocks(text)

        identity = {}
        if "1. Vessel Identity" in sections or "Vessel Identity" in sections:
            sec = sections.get("1. Vessel Identity", sections.get("Vessel Identity", ""))
            for m in re.finditer(r"\*\*([^*]+)\*\*:\s*([^\n]+)", sec):
                identity[m.group(1).strip()] = m.group(2).strip()
        cards["vessel_identity"] = identity

        status = {}
        if "2. Current Status" in sections or "Current Status" in sections:
            sec = sections.get("2. Current Status", sections.get("Current Status", ""))
            for m in re.finditer(r"\*\*([^*]+)\*\*:\s*([^\n]+)", sec):
                status[m.group(1).strip()] = m.group(2).strip()
        cards["current_status"] = status

        if "3. Port Call History" in sections:
            tables = extract_tables(sections["3. Port Call History"])
            if tables:
                cards["port_calls"] = tables[0]["rows"]

        if "4. Internet Attack Surface" in sections or "Attack Surface" in sections:
            cards["shodan"] = {"summary": "See analyst report for details"}

        if "7. Risk Tier" in sections or "7. Risk Tier & Triggers" in sections:
            sec = sections.get("7. Risk Tier", sections.get("7. Risk Tier & Triggers", ""))
            cards["analysis"] = {"risk_tier": "LOW"}
            for m in re.finditer(r"\*\*([^*]+)\*\*:\s*([^\n]+)", sec):
                if "tier" in m.group(1).lower():
                    cards["analysis"]["risk_tier"] = m.group(2).strip()

    # Red team playbook
    pb_path = report_dir / "red-team-playbook.md"
    if pb_path.exists():
        text = pb_path.read_text()
        sections = parse_section_blocks(text)
        vectors = []
        for heading, content in sections.items():
            m = re.match(r"Vector ([A-Z]+): (.+)", heading)
            if m:
                vec = {"name": f"{m.group(1)}: {m.group(2)}", "steps": [], "detection_points": []}
                for line in content.split("\n"):
                    l = line.lower()
                    if "difficulty:" in l:
                        vec["difficulty"] = "MEDIUM"
                    if "cost:" in l:
                        vec["cost"] = ""
                for line in content.split("\n"):
                    ms = re.match(r"\d+\.\s+(.+)", line.strip())
                    if ms:
                        vec["steps"].append(ms.group(1))
                tables = extract_tables(content)
                for t in tables:
                    if "Detection Point" in str(t["headers"]):
                        for row in t["rows"]:
                            vec["detection_points"].append(row)
                vectors.append(vec)
        cards["red_team_playbook"] = {"vectors": vectors}

    return cards


def render(report_dir, mode=None):
    """
    Main entry point. Reads markdown report files from report_dir
    and returns structured JSON for the dashboard frontend.
    Auto-detects mode from filenames if not provided.
    """
    report_dir = Path(report_dir)
    if not report_dir.exists():
        return {"error": f"Report directory not found: {report_dir}"}

    # Auto-detect mode from filenames
    if mode is None:
        files = {f.name for f in report_dir.glob("*.md")}
        if "red-team-playbook.md" in files or "indicators-and-detection.md" in files:
            mode = "vessel"
        elif "research-impact-analysis.md" in files or "affiliation-timeline.md" in files:
            mode = "person"
        else:
            mode = "person"  # default

    if mode == "person":
        cards = render_person_report(report_dir)
    else:
        cards = render_vessel_report(report_dir)

    cards["mode"] = mode
    cards["report_dir"] = str(report_dir)
    return cards
