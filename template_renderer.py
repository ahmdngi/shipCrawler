#!/usr/bin/env python3
"""
Jinja2 template renderer for ShipCrawler vessel OSINT report skeletons.

Renders skeleton markdown files at scan start using known identity fields
(vessel name, IMO, MMSI, callsign if provided). The agent then fills in
the <!-- --> comment placeholders during research.

Templates live in templates/ alongside this module:
  - vessel-analyst-report.j2
  - vessel-red-team-playbook.j2
  - vessel-indicators-and-detection.j2
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader
    _JINJA_AVAILABLE = True
except ImportError:
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]
    _JINJA_AVAILABLE = False


FRAMEWORK_VERSION = "7.3"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_env() -> "Environment":
    """Create a Jinja2 environment with the templates directory."""
    if not _JINJA_AVAILABLE:
        raise ImportError(
            "jinja2 is required for template rendering. "
            "Install with: pip install jinja2"
        )
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,  # markdown, not HTML
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env


def render_skeleton(
    template_name: str,
    vessel_name: str,
    imo: str | None = None,
    mmsi: str | None = None,
    callsign: str | None = None,
    date: str | None = None,
    report_dir: str = "",
    **kwargs: Any,
) -> str:
    """Render a report skeleton template with known vessel identity fields.

    Args:
        template_name: Template filename (e.g. "vessel-analyst-report.j2").
        vessel_name: Vessel name (will be uppercased in templates).
        imo: IMO number if known (None = agent discovers).
        mmsi: MMSI if known (None = agent discovers).
        callsign: Call sign if known (None = agent discovers).
        date: Investigation date (YYYY-MM-DD). Defaults to today.
        report_dir: Absolute path to the report output directory.
        **kwargs: Additional template variables.

    Returns:
        Rendered markdown string with skeleton placeholders for the agent
        to fill in.
    """
    from datetime import date as date_cls

    env = _get_env()
    template = env.get_template(template_name)

    if date is None:
        date = date_cls.today().isoformat()

    return template.render(
        vessel_name=vessel_name,
        imo=imo,
        mmsi=mmsi,
        callsign=callsign,
        date=date,
        report_dir=report_dir,
        framework_version=FRAMEWORK_VERSION,
        **kwargs,
    )


def render_vessel_skeletons(
    vessel_name: str,
    report_dir: str | Path,
    imo: str | None = None,
    mmsi: str | None = None,
    callsign: str | None = None,
    date: str | None = None,
) -> dict[str, str]:
    """Render all three vessel report skeletons and return them.

    Returns:
        Dict mapping filename → rendered markdown:
        {
            "analyst-report.md": "...",
            "red-team-playbook.md": "...",
            "indicators-and-detection.md": "...",
        }
    """
    report_dir = str(report_dir)
    common = dict(
        vessel_name=vessel_name,
        imo=imo,
        mmsi=mmsi,
        callsign=callsign,
        date=date,
        report_dir=report_dir,
    )
    return {
        "analyst-report.md": render_skeleton(
            "vessel-analyst-report.j2", **common
        ),
        "red-team-playbook.md": render_skeleton(
            "vessel-red-team-playbook.j2", **common
        ),
        "indicators-and-detection.md": render_skeleton(
            "vessel-indicators-and-detection.j2", **common
        ),
    }


def write_skeleton_files(
    vessel_name: str,
    report_dir: str | Path,
    imo: str | None = None,
    mmsi: str | None = None,
    callsign: str | None = None,
    date: str | None = None,
) -> list[Path]:
    """Render all three vessel skeletons and write them to report_dir.

    Returns:
        List of written file paths.
    """
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    skeletons = render_vessel_skeletons(
        vessel_name=vessel_name,
        report_dir=report_dir,
        imo=imo,
        mmsi=mmsi,
        callsign=callsign,
        date=date,
    )

    written = []
    for filename, content in skeletons.items():
        path = report_dir / filename
        path.write_text(content)
        written.append(path)

    return written


def is_jinja_available() -> bool:
    """Check if jinja2 is installed."""
    return _JINJA_AVAILABLE
