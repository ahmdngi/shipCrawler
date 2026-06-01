#!/usr/bin/env python3
"""Person & vessel analysis — research impact, confidence, affiliation timeline, targeting scenarios."""

import re
from datetime import datetime


# ═════════════════════════════════════════════════════════════════════════════════
# PERSON ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════════

def generate_person_analysis(person_data, social_media=None):
    """Generate analysis for person OSINT — enriched with academic metrics."""
    analysis = {
        "risk_tier": "LOW",
        "confidence": "MEDIUM",
        "exposure_score": 0,
        "notes": [],
        "recommendations": [],
    }
    emails = person_data.get("emails", [])
    social = social_media or person_data.get("social_media", [])
    publications = person_data.get("publications", [])
    citation_metrics = person_data.get("citation_metrics", {})
    coauthors = person_data.get("coauthors", [])
    professional_history = person_data.get("professional_history", [])

    score = 0
    num_sources = len(person_data.get("raw_data_sources", []))

    # Exposure scoring
    if emails:
        score += 10
        analysis["notes"].append(f"{len(emails)} email address(es) identified")
    if social:
        score += min(len(social) * 3, 20)
        platforms = sorted(set(s.get("platform", "?") for s in social))
        analysis["notes"].append(f"Profiles on {len(platforms)} platform(s): {', '.join(platforms[:6])}")

    if publications:
        score += 5
        total_pubs = len(publications)
        analysis["notes"].append(f"{total_pubs} publication(s) identified across sources")

    if citation_metrics:
        h = citation_metrics.get("h_index", 0)
        c = citation_metrics.get("total_citations", 0)
        if h > 0:
            score += min(h, 10)
            analysis["notes"].append(f"h-index: {h}, Total citations: {c:,}" if c else f"h-index: {h}")

    if professional_history:
        score += len(professional_history) * 2
        roles = [h.get("role", "") for h in professional_history if h.get("role")]
        if roles:
            analysis["notes"].append(f"Career: {' → '.join(roles[:3])}")

    if coauthors:
        score += min(len(coauthors), 5)
        top = sorted(coauthors, key=lambda c: c.get("shared_papers", 0), reverse=True)[:3]
        names = [c["name"] for c in top]
        analysis["notes"].append(f"Top co-authors: {', '.join(names)}")

    # Confidence based on number of independent sources
    if num_sources >= 4:
        analysis["confidence"] = "HIGH"
        analysis["notes"].append(f"Data from {num_sources} independent sources — HIGH confidence")
    elif num_sources >= 2:
        analysis["confidence"] = "MEDIUM"
        analysis["notes"].append(f"Data from {num_sources} independent sources — MEDIUM confidence")
    else:
        analysis["confidence"] = "LOW"
        analysis["notes"].append("Limited data — LOW confidence")

    # Risk tier
    if score >= 25:
        analysis["risk_tier"] = "HIGH"
        analysis["recommendations"].append(
            "High digital exposure — academic researcher with extensive online footprint. "
            "Enable MFA on ORCID, institutional accounts, and publisher portals."
        )
    elif score >= 12:
        analysis["risk_tier"] = "MEDIUM"
        analysis["recommendations"].append(
            "Moderate digital footprint — review social media privacy settings. "
            "Use a password manager to prevent credential cascade across academic platforms."
        )
    else:
        analysis["recommendations"].append("Low digital exposure — minimal action required")

    analysis["recommendations"].append(
        "Periodically audit ORCID publication list for unauthorized additions."
    )
    analysis["exposure_score"] = min(score, 100)
    return analysis


# ═════════════════════════════════════════════════════════════════════════════════
# RESEARCH IMPACT ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════════

def generate_research_impact(publications, citation_metrics, coauthors):
    """Generate structured research impact analysis."""
    impact = {
        "total_publications": len(publications),
        "citation_metrics": citation_metrics,
        "publications_by_year": {},
        "top_publications": citation_metrics.get("top_publications", [])[:5],
        "coauthor_count": len(coauthors),
        "top_coauthors": sorted(coauthors, key=lambda c: c.get("shared_papers", 0), reverse=True)[:5],
        "first_year": None,
        "last_year": None,
        "career_span_years": 0,
    }

    # Group by year
    years = {}
    for pub in publications:
        y = pub.get("year", "")
        if y and y.isdigit():
            years[y] = years.get(y, 0) + 1
    impact["publications_by_year"] = dict(sorted(years.items()))

    # Career span
    year_keys = sorted(years.keys())
    if year_keys:
        impact["first_year"] = int(year_keys[0])
        impact["last_year"] = int(year_keys[-1])
        impact["career_span_years"] = impact["last_year"] - impact["first_year"]

    return impact


# ═════════════════════════════════════════════════════════════════════════════════
# AFFILIATION TIMELINE
# ═════════════════════════════════════════════════════════════════════════════════

def generate_affiliation_timeline(professional_history, education):
    """Generate structured affiliation timeline."""
    timeline = {
        "current_positions": [],
        "past_positions": [],
        "education": education,
        "total_roles": len(professional_history),
        "geographic_summary": "",
    }

    for h in professional_history:
        entry = {
            "role": h.get("role", ""),
            "organization": h.get("company", ""),
            "department": h.get("department", ""),
            "period": h.get("period", ""),
        }
        period = h.get("period", "")
        if "Present" in period or not h.get("end"):
            timeline["current_positions"].append(entry)
        else:
            timeline["past_positions"].append(entry)

    # Geographic mobility summary
    locations = set()
    for h in professional_history:
        org = h.get("company", "")
        if "Tallinn" in org or "TalTech" in org or "Estonian Maritime" in org or "Estonia" in org:
            locations.add("Estonia")
        if "Østfold" in org or "HiØ" in org or "Norway" in org or "NTNU" in org or "Norwegian" in org:
            locations.add("Norway")
        if "Mainz" in org or "Germany" in org or "Johannes Gutenberg" in org:
            locations.add("Germany")
    if locations:
        timeline["geographic_summary"] = ", ".join(sorted(locations))

    return timeline


# ═════════════════════════════════════════════════════════════════════════════════
# TARGETING SCENARIOS (Person OSINT)
# ═════════════════════════════════════════════════════════════════════════════════

def generate_person_targeting_scenarios(person_data, social_media):
    """Generate targeting scenarios based on person's profile type."""
    role = (person_data.get("role", "") or "").lower()
    employer = (person_data.get("employer", "") or "").lower()
    has_academic = any(k in employer for k in ["university", "college", "institute", "academy"])
    has_publications = bool(person_data.get("publications", []))
    emails = person_data.get("emails", [])
    professional_history = person_data.get("professional_history", [])

    vectors = []

    # Vector A: Academic Pretexting (for researchers with publications)
    if has_academic or has_publications:
        vector_a = {
            "name": "A: Academic Pretexting (Fake CFP / Conference Scam)",
            "difficulty": "LOW",
            "cost": "$50–200",
            "detection_prob": "LOW",
            "rationale": "Academic researcher with publicly listed email and publication record is susceptible to fake CFP emails that exploit the culture of peer review.",
            "equipment": [
                "Domain registration (typosquatted conference domain, $10–15/yr)",
                "Email hosting (ProtonMail or custom, $0–50)",
                "Basic web page with credential-harvesting form ($20–100)",
                "VPN / VPS to obfuscate origin ($10–20/mo)",
            ],
            "steps": [
                "Collect CFP submission history from Google Scholar / ORCID — identify recurring conferences",
                "Register lookalike domain (e.g., ieee-maritime-2026.com)",
                "Craft spoofed CFP email referencing researcher's specific topics",
                "Deploy credential harvesting via fake submission portal",
                "Optionally deliver malware after credential capture (macro-enabled PDF)",
                "Escalate via harvested institutional credentials",
            ],
            "detection_points": [
                {"point": "Email from spoofed academic domain", "signal": "SPF/DMARC fail on CFP email", "tool": "Email gateway / MISP"},
                {"point": "New/suspicious domain registration", "signal": "Domain aged <30 days matching known conference", "tool": "DNS logs / Whois"},
                {"point": "Credential submission to non-institutional domain", "signal": "Login event from unusual IP", "tool": "SIEM correlation"},
            ],
        }
        vectors.append(vector_a)

    # Vector B: Credential Cascade (if multiple platforms identified)
    num_platforms = len(social_media) if social_media else 0
    if num_platforms >= 3 or len(emails) >= 2:
        vector_b = {
            "name": "B: Credential Cascade Exploitation",
            "difficulty": "MEDIUM",
            "cost": "$0–50",
            "detection_prob": "HIGH (with MFA)",
            "rationale": f"Researcher maintains accounts across {num_platforms} academic platforms — common password reuse across ORCID, Google Scholar, institutional email, and publisher portals creates cascade risk.",
            "equipment": [
                "Breach database access (HIBP, DeHashed)",
                "Password spray tool (Hydra, Crowbar)",
                "Email enumeration tool (Hunter.io)",
                "Residential proxies to avoid rate limiting",
            ],
            "steps": [
                f"Harvest emails from person profile: {', '.join(emails[:3])}",
                "Check known breach databases for compromised credentials",
                "If breach data found: spray across institutional services, ORCID, ResearchGate",
                "Exploit single sign-on: one institutional credential grants access to email, cloud storage, Teams recordings",
                "Lateral movement: target co-authors with spear-phishing from compromised email",
            ],
            "detection_points": [
                {"point": "Multiple failed logins (5+ in 60s)", "signal": "Brute-force attempt", "tool": "Wazuh / Elastic auth logs"},
                {"point": "Login from unusual geographic location", "signal": "Estonia-based account accessed from non-EU IP", "tool": "Azure AD / IDS"},
                {"point": "MFA challenge spike", "signal": "Multiple MFA prompts in short window", "tool": "MFA provider logs"},
                {"point": "Email auto-forward rule added", "signal": "Unusual forwarding rule in webmail", "tool": "Exchange / Office 365 audit"},
            ],
        }
        vectors.append(vector_b)

    # Vector C: ORCID/Profile Takeover (if publications identified)
    if has_publications:
        vector_c = {
            "name": "C: Academic Profile / ORCID Takeover",
            "difficulty": "LOW–MEDIUM",
            "cost": "$20",
            "detection_prob": "MEDIUM",
            "rationale": "ORCID accounts have weak recovery mechanisms. Takeover allows polluting publication records, impersonation for grant fraud, and fake peer review.",
            "equipment": [
                "Domain + email for fake institutional recovery",
                "Breach data for password hint identification",
            ],
            "steps": [
                "Identify ORCID account recovery vector (linked email)",
                "Initiate password reset; intercept if linked email is compromised",
                "Add fraudulent publications to inflate citation metrics",
                "Change affiliation to fictional institution",
                "Use verified ORCID OAuth to access other academic services",
                "Impersonate in peer review — fraudulently accept/reject papers",
            ],
            "detection_points": [
                {"point": "ORCID email change notification", "signal": "'Your ORCID email has been changed' alert", "tool": "User awareness (no auto-detect)"},
                {"point": "Suspicious publications added", "signal": "Publications from unrelated fields", "tool": "ORCID audit / manual review"},
                {"point": "Linked account compromise", "signal": "Google Scholar / Scopus login from new device", "tool": "Platform security alerts"},
            ],
        }
        vectors.append(vector_c)

    # Vector D: Supply Chain / Dependency Attack (if GitHub or tools publisher)
    if social_media:
        has_github = any("github" in s.get("url", "").lower() for s in social_media)
        if has_github:
            vector_d = {
                "name": "D: Open-Source Supply Chain Attack",
                "difficulty": "MEDIUM",
                "cost": "$0–100",
                "detection_prob": "MEDIUM",
                "rationale": "GitHub presence suggests the researcher may maintain or contribute to open-source tools — a vector for dependency typosquatting or malicious PR injection.",
                "equipment": [
                    "GitHub account for PR submission",
                    "PyPI / npm account for package typosquatting",
                    "Dependency analysis tools",
                ],
                "steps": [
                    "Identify maintained repositories from GitHub profile",
                    "Analyze dependencies for typosquatting opportunities",
                    "Submit malicious PR with backdoor in dependency update",
                    "Alternatively: register typosquatted package name on PyPI/npm",
                    "Wait for automated or manual dependency update",
                ],
                "detection_points": [
                    {"point": "Suspicious PR from unknown contributor", "signal": "PR with unusual binary or minified code", "tool": "GitHub audit / CodeQL"},
                    {"point": "New PyPI/npm package with similar name", "signal": "Package name matches existing dependency with character substitution", "tool": "Package registry monitoring"},
                ],
            }
            vectors.append(vector_d)

    summary = ""
    if vectors:
        summary = f"Target persona: academic researcher. {len(vectors)} attack vectors identified based on digital footprint."

    return {
        "vectors": vectors,
        "summary": summary,
        "person_type": "academic_researcher" if has_academic else "professional",
    }


# ═════════════════════════════════════════════════════════════════════════════════
# CONFIDENCE ASSESSMENT
# ═════════════════════════════════════════════════════════════════════════════════

def generate_person_confidence(person_data, sources_count):
    """Generate per-category confidence assessment."""
    confidence = {
        "overall": "LOW",
        "categories": {},
    }

    categories = {
        "Identity": bool(person_data.get("name")),
        "Affiliation": bool(person_data.get("employer")),
        "Employment History": len(person_data.get("professional_history", [])) > 0,
        "Publications": len(person_data.get("publications", [])) > 0,
        "Social Media Presence": len(person_data.get("social_media", [])) > 0,
    }

    high_count = 0
    medium_count = 0
    for cat, has_data in categories.items():
        if has_data and sources_count >= 3:
            confidence["categories"][cat] = "HIGH"
            high_count += 1
        elif has_data and sources_count >= 1:
            confidence["categories"][cat] = "MEDIUM"
            medium_count += 1
        else:
            confidence["categories"][cat] = "LOW"

    if high_count >= 3:
        confidence["overall"] = "HIGH"
    elif high_count + medium_count >= 2:
        confidence["overall"] = "MEDIUM"

    return confidence


# ═════════════════════════════════════════════════════════════════════════════════
# VESSEL ANALYSIS (existing, preserved)
# ═════════════════════════════════════════════════════════════════════════════════

def generate_red_team_playbook(vessel_type, vessel_info):
    """Auto-generate a red-team playbook based on vessel type."""
    vtype = (vessel_type or "").lower()
    playbook = {
        "vessel_type": vessel_type or "Unknown",
        "risk_tier": vessel_info.get("analysis", {}).get("risk_tier", "LOW"),
        "vectors": [],
        "summary": ""
    }

    if any(k in vtype for k in ["pleasure", "yacht", "sail"]):
        playbook["vectors"] = [
            {
                "name": "A: USB Drop & Cellular MiTM",
                "difficulty": "LOW", "cost": "$200-500", "detection_prob": "LOW",
                "equipment": ["USB Rubber Ducky ($70)", "Yagi antenna + HackRF ($350)", "Raspberry Pi 4 with LTE modem ($150)"],
                "steps": [
                    "Deploy USB Rubber Ducky at marina gangway or crew common area",
                    "Set up cellular MiTM using Yagi antenna pointed at vessel's LTE antenna",
                    "Capture unencrypted traffic (NMEA 0183 over UDP, passenger WiFi)",
                    "Exfiltrate navigation data and identify VSAT/Starlink credentials"
                ],
                "detection_points": [
                    {"point": "Unknown USB device insertion", "signal": "Kernel USB event log", "tool": "Wazuh / Osquery"},
                    {"point": "Rogue LTE tower (LAC mismatch)", "signal": "LTE cell ID ≠ known tower", "tool": "Cell monitor / Kraken"},
                    {"point": "Data exfiltration spike", "signal": "Uplink traffic > 2x baseline", "tool": "Zeek / Elastic"}
                ]
            },
            {
                "name": "B: AIS Spoofing — Proxy Vessel",
                "difficulty": "MEDIUM", "cost": "$1,500-3,000", "detection_prob": "MEDIUM",
                "equipment": ["AIS transceiver (commercial grade, $800)", "SDR (RTL-SDR + upconverter, $50)", "Laptop with OpenCPN + AIS spoofing script"],
                "steps": [
                    "Research target's route pattern from AIS history",
                    "Spawn ghost AIS signal showing target vessel at false position",
                    "Simulate deviation toward congested chokepoint",
                    "Observe real-world response (VTS, other vessels altering course)",
                    "Second phase: replay target's identity on a proxy vessel in different port"
                ],
                "detection_points": [
                    {"point": "MMSI appearing in two locations simultaneously", "signal": "Duplicate MMSI alert", "tool": "AIS correlation / Elastic"},
                    {"point": "Rapid position changes (>60 kn for pleasure craft)", "signal": "Speed anomaly", "tool": "AIS monitor"},
                    {"point": "Missing Class-B transponder data", "signal": "AIS signal without SOTDMA", "tool": "RF analysis"}
                ]
            }
        ]
        playbook["summary"] = "Pleasure craft have limited internet exposure but are vulnerable to physical access attacks (USB drops) and cellular interception."

    elif any(k in vtype for k in ["cargo", "tanker", "bulk", "container"]):
        playbook["vectors"] = [
            {
                "name": "A: VSAT Exploit (SAILOR / KVH)",
                "difficulty": "MEDIUM", "cost": "$0-500", "detection_prob": "MEDIUM",
                "equipment": ["Laptop with Shodan/Censys access", "Default credential lists", "Metasploit (KVH exploit module)"],
                "steps": [
                    "Scan Shodan for exposed SAILOR 900 / KVH management interfaces",
                    "Test default credentials (admin:1234, admin:password)",
                    "If access gained: exfiltrate GPS, AIS relay data, crew email",
                    "Deploy persistent backdoor via firmware update mechanism"
                ],
                "detection_points": [
                    {"point": "Unauthenticated VSAT admin login", "signal": "VSAT panel access from unknown IP", "tool": "Shodan alert / Elastic"},
                    {"point": "Firmware file modified", "signal": "Checksum mismatch on VSAT firmware", "tool": "Wazuh FIM"},
                    {"point": "C2 beaconing from VSAT", "signal": "Periodic HTTPS to uncommon ASN", "tool": "Zeek / Elastic"}
                ]
            },
            {
                "name": "B: Signal K / NMEA-over-IP Abuse",
                "difficulty": "LOW", "cost": "$0", "detection_prob": "LOW",
                "equipment": ["Laptop", "Signalk-to-NMEA converter tools"],
                "steps": [
                    "Query Shodan for exposed Signal K servers on port 3000",
                    "Access signalk API to read live navigation, engine, environmental data",
                    "If authenticated: inject false sensor data (GPS offset, depth, wind)"
                ],
                "detection_points": [
                    {"point": "Signal K API accessed from external IP", "signal": "signalk REST logs", "tool": "Signal K audit log / Elastic"},
                    {"point": "Sensor data deviation from expected", "signal": "GPS position delta > threshold", "tool": "ECDIS / Elastic"}
                ]
            }
        ]
        playbook["summary"] = "Commercial vessels with VSAT and integrated bridge systems have significant internet exposure."

    elif any(k in vtype for k in ["passenger", "ferry", "cruise"]):
        playbook["vectors"] = [
            {
                "name": "A: Passenger WiFi MiTM",
                "difficulty": "LOW", "cost": "$300-800", "detection_prob": "MEDIUM",
                "equipment": ["WiFi Pineapple ($200)", "Laptop with Wireshark", "Captive portal cracking tools"],
                "steps": [
                    "Board vessel as passenger, connect to onboard WiFi",
                    "Deploy WiFi Pineapple in evil twin mode",
                    "Capture credentials, payment data, crew portal access",
                    "Lateral movement from passenger network to OT network via flat VLAN"
                ],
                "detection_points": [
                    {"point": "Rogue access point detected", "signal": "BSSID mismatch", "tool": "WIPS / Elastic"},
                    {"point": "Unusual DNS queries from passenger segment", "signal": "DNS to known C2 domains", "tool": "Zeek / Elastic"},
                    {"point": "Lateral traffic to OT subnet", "signal": "Passenger IP connecting to bridge", "tool": "Elastic / Zeek"}
                ]
            },
            {
                "name": "B: ECDIS GPS Spoofing",
                "difficulty": "HIGH", "cost": "$5,000+", "detection_prob": "HIGH",
                "equipment": ["SDR (USRP B210, $1,200)", "GPS spoofing transmitter", "Laptop with GPS-SDR-SIM"],
                "steps": [
                    "Research vessel's ECDIS make and GPS antenna location",
                    "Transmit spoofed GPS signal with gradual position offset",
                    "Observe if crew detects deviation (test vigilance)",
                    "Escalate to full position hijack to misroute vessel"
                ],
                "detection_points": [
                    {"point": "GPS signal strength anomaly", "signal": "GNSS jamming/spoofing detected", "tool": "GPS monitor / Resilient PNT"},
                    {"point": "Radar/AIS/ECDIS position mismatch", "signal": "Three-source discrepancy", "tool": "Integrated bridge alarm"},
                    {"point": "Course deviation without command", "signal": "Autopilot receiving false GPS input", "tool": "ECDIS audit log"}
                ]
            }
        ]
        playbook["summary"] = "Passenger vessels present dual attack surface: passenger-facing IT networks and bridge OT systems."

    else:
        playbook["vectors"] = [{
            "name": "A: Shodan Surface Recon",
            "difficulty": "LOW", "cost": "$0", "detection_prob": "LOW",
            "equipment": ["Laptop with Shodan access"],
            "steps": [
                "Scan Shodan for vessel name, MMSI, and associated maritime services",
                "Document all open ports, banners, and CVEs",
                "Identify VSAT, Signal K, or NMEA services accessible from internet"
            ],
            "detection_points": [
                {"point": "Shodan scanner probe", "signal": "Connection from Shodan IP range", "tool": "Firewall logs / Elastic"}
            ]
        }]
        playbook["summary"] = "Vessel type undetermined. Generic Shodan reconnaissance to establish attack surface baseline."

    return playbook


def generate_detection_rules(vessel_type):
    """Auto-generate M-SOC detection rules based on vessel type."""
    vtype = (vessel_type or "").lower()
    rules = {
        "indicators": [
            {"id": "I-001", "type": "Network", "phase": "Recon", "priority": "HIGH",
             "description": "Shodan scan detected against vessel IP range"},
            {"id": "I-002", "type": "Network", "phase": "Initial Access", "priority": "HIGH",
             "description": "VSAT management interface login from unrecognized IP"},
            {"id": "I-003", "type": "Network", "phase": "C2", "priority": "MEDIUM",
             "description": "Periodic HTTPS beaconing to uncommon ASN from bridge network"},
            {"id": "I-004", "type": "AIS/RF", "phase": "Impact", "priority": "HIGH",
             "description": "MMSI duplication — same vessel ID broadcasting from two locations"},
            {"id": "I-005", "type": "AIS/RF", "phase": "Recon", "priority": "MEDIUM",
             "description": "AIS signal without valid SOTDMA or CSTDMA structure"},
            {"id": "I-006", "type": "Physical", "phase": "Initial Access", "priority": "MEDIUM",
             "description": "Unknown USB mass storage device connected to bridge computer"},
            {"id": "I-007", "type": "Cellular", "phase": "Initial Access", "priority": "MEDIUM",
             "description": "Cellular tower LAC mismatch — possible rogue tower operation"},
        ],
        "elastic_rules": [
            {"name": "MMSI Duplicate Detection", "type": "threshold",
             "query": "event.dataset: ais AND vessel.mmsi: *", "condition": "cardinality(vessel.position.lat) > 1"},
            {"name": "VSAT Admin Login Alert", "type": "query",
             "query": 'source.ip: * AND http.request.method: POST AND url.path: "/cgi-bin/login"'},
            {"name": "Unauthorized USB Device", "type": "query",
             "query": 'event.action: "device_inserted" AND not process.name: "systemd-udevd"'},
            {"name": "C2 Beacon Detection", "type": "threshold",
             "query": 'network.protocol: tls AND destination.asn.organization: "Unknown"',
             "condition": "count > 50 in 5m"},
        ],
        "zeek_scripts": [
            {"name": "ais-radar-correlation.zeek",
             "description": "Correlates AIS position reports with radar tracks."},
            {"name": "c2-beacon-detect.zeek",
             "description": "Detects periodic TLS connections to uncommon destinations."},
        ],
        "wazuh_rules": [
            {"name": "USB Device Detection",
             "rule_xml": '<rule id="100201" level="10"><if_group>syscheck</if_group><field name="event">added</field><field name="type">usb</field><description>USB device connected to bridge system</description></rule>'},
            {"name": "Process from External Volume",
             "rule_xml": '<rule id="100202" level="12"><if_group>syscheck</if_group><field name="path">/media/</field><description>Process spawned from external volume</description></rule>'},
        ],
        "grafana_alerts": [
            {"name": "Bridge Network Anomaly",
             "query": 'sum(rate(ais_duplicate_mmsi_total[5m])) > 0',
             "message": "MMSI collision detected — possible AIS spoofing"},
            {"name": "VSAT Traffic Spike",
             "query": 'sum(rate(vsat_bytes_total[5m])) > 2 * avg(sum(rate(vsat_bytes_total[1h])))',
             "message": "Unusual VSAT traffic — potential data exfiltration"},
        ],
        "runbook": {
            "AIS_001_MMSI_Duplicate": {"triage": [
                "1. Check both positions on MarineTraffic and VesselFinder",
                "2. Cross-reference with AIS class and signal strength",
                "3. If both Class A, contact VTS for confirmation",
                "4. Run RF direction finding to locate rogue transmitter",
                "5. If unverified within 15 min, escalate to maritime security",
            ]},
            "NET_001_VSAT_Intrusion": {"triage": [
                "1. Verify source IP against known crew/office VPN ranges",
                "2. Check VSAT management logs for login timestamps",
                "3. If unauthorized: disable remote management immediately",
                "4. Capture full packet capture from bridge firewall",
                "5. Initiate VSAT credential rotation",
            ]},
            "PHY_001_USB_Drop": {"triage": [
                "1. Locate the bridge computer that logged the USB event",
                "2. Physically inspect for unknown USB devices",
                "3. Quarantine the affected system from shipboard network",
                "4. Run antivirus and forensic analysis",
                "5. Report to M-SOC with device serial and timestamp",
            ]},
        }
    }

    if any(k in vtype for k in ["passenger", "ferry", "cruise"]):
        rules["indicators"].extend([
            {"id": "I-008", "type": "Network", "phase": "Lateral Movement", "priority": "HIGH",
             "description": "Traffic from passenger WiFi subnet to bridge OT subnet"},
        ])
    elif any(k in vtype for k in ["cargo", "tanker"]):
        rules["indicators"].extend([
            {"id": "I-008", "type": "Network", "phase": "Impact", "priority": "HIGH",
             "description": "ECDIS chart data modified outside of scheduled update window"},
        ])

    return rules


def analyze_vessel(vessel_info, shodan_data):
    """Generate operational analysis based on available data."""
    analysis = {"home_zone": "Unknown", "pattern": "Unknown", "risk_tier": "LOW", "confidence": "LOW", "notes": []}

    flag = vessel_info.get("flag", "")
    if flag:
        analysis["notes"].append(f"Flag state: {flag}")

    shodan_total = shodan_data.get("total", 0)
    if shodan_total == 0:
        analysis["pattern"] = "Limited digital footprint — no public-facing IT/OT systems detected"
        analysis["risk_tier"] = "LOW"
    elif shodan_total <= 3:
        analysis["pattern"] = "Minimal digital exposure — few internet-facing systems"
        analysis["risk_tier"] = "MEDIUM"
    else:
        analysis["pattern"] = "Significant digital footprint — multiple internet-facing systems"
        analysis["risk_tier"] = "HIGH"

    for svc in shodan_data.get("results", []):
        if svc.get("port") in {23, 21, 3389}:
            analysis["risk_tier"] = "HIGH"
    if any(s.get("port") == 3000 for s in shodan_data.get("results", [])):
        if analysis["risk_tier"] == "LOW":
            analysis["risk_tier"] = "MEDIUM"

    filled = sum(1 for v in vessel_info.values() if v)
    analysis["confidence"] = "HIGH" if filled >= 5 else ("MEDIUM" if filled >= 3 else "LOW")
    return analysis
