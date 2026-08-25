# ShipCrawler — OSINT Methodology (Skill)

**Version:** 1.0.0 | **License:** MIT | **Author:** Ahmed Nagi Nasr

This is the reproducible methodology skill that drives the ShipCrawler agent during vessel investigations. It is the public, paper-facing distillation of the operational skill used in the IEEE Access validation (Access-2026-38078, June–July 2026). It contains the full investigation methodology — phases, source chains, confidence protocol, reporting standards, and ethical constraints — sufficient to reproduce the validation methodology.

For the platform implementation (worker, dashboard, queue), see the repository root.

---

## Framework

ShipCrawler implements the OSINT Maritime Framework (Nasr et al., IEEE Access 2026) as an agent-driven reconnaissance methodology. Each vessel investigation executes five phases against public sources, producing a three-file intelligence package plus a methodology appendix.

The methodology is **agent-driven and adaptive**: the agent selects tools and follow-up leads phase by phase based on intermediate results, cross-references multiple independent sources, and documents confidence per finding. It is **probabilistic by design** — successive runs may take different investigation paths; the destination (complete intelligence package) is constant.

---

## Investigation Phases

### Phase 0: Vessel Identity (Equasis — primary registry)

Establish authoritative vessel identity before any other collection.

**Primary tool:** `equasis` CLI (`equasis vessel --imo <IMO>`), returns: IMO, name, flag, call sign, MMSI, GT, DWT, type, year built, status, management companies, classification societies, PSC inspections, historical names/flags.

- On rate limiting ("VESSEL NOT FOUND" + parse failure), wait 30–60 s and retry.
- Equasis locks accounts after ~10 login attempts in a short window; batch queries within one session.
- Fallback (CLI unavailable): browser-based access to the Equasis registry.

**Output:** authoritative IMO, MMSI, name, flag, ownership chain, classification status, PSC history.

### Phase 1: Target Identification (AIS)

Establish current position, movement, and port-call behaviour from at least two independent AIS sources:

- MarineTraffic (MMSI-based details page)
- VesselFinder (MMSI-based details page)
- MyShipTracking / Seatospace / AISVesselTracker (MMSI-based)

**Extraction pattern:** discover MMSI via search if unknown, then extract structured data from each AIS source by MMSI. Cross-reference all sources; flag discrepancies. 3+ independent sources = HIGH confidence on identity and position.

**Behavioural analysis:** speed profile, port call history, home zone, recurring routes, anchorage vs. moored ratio, AIS dark periods (>12 h near sanctioned ports), false destination fields.

### Phase 2: Attack Surface Discovery (Shodan)

Query Shodan by vessel name, MMSI, IMO, call sign, and historical names. Search maritime-specific protocols:

- Signal K servers (port 3000)
- VSAT management interfaces (Cobham SAILOR 900, KVH, Intellian)
- NMEA-over-IP gateways, ECDIS, AIS receivers
- Region filters for Baltic/port cities

**Critical rule:** report zero results explicitly. A negative Shodan result means *no vessel-attributable exposure was identified* — it does not prove absence of internet-facing systems (dynamic addressing, carrier NAT, shared satellite infrastructure, banner limits, scan coverage).

### Phase 3: Vulnerability Assessment

- Compare discovered services against known maritime CVEs (VSAT terminals, ECDIS, GPS receivers).
- Shodan exploit search per discovered product.
- Check for default credentials and misconfigurations on maritime equipment (exposed APIs, unauthenticated interfaces).
- Document risk level per finding.

### Phase 4: Threat Intelligence Integration

- Cross-reference findings with maritime cyber incident databases.
- Correlate with sanctions lists (OpenSanctions, Ukraine War & Sanctions, national lists).
- Check investigative-journalism databases (e.g., OCCRP) for shell-company networks and ownership obfuscation.
- Generate threat brief with actionable recommendations; feed indicators into M-SOC (Elasticsearch, MISP, Zeek, Wazuh).

### Phase 5: Analysis & Reporting

Produce a structured deliverable folder:

```
<vessel-name>-report/
├── analyst-report.md           # Full OSINT findings (identity, position, port calls, Shodan, confidence)
├── red-team-playbook.md        # Attack scenario design (kill chain, vectors, detection points)
├── indicators-and-detection.md # M-SOC config (Elastic rules, Zeek scripts, Wazuh rules)
└── methodology-appendix.md     # Investigation operations stats (time, tool calls, sources, failures)
```

**Report contents:**
- *analyst-report.md*: vessel identity; current position/status; port-call history; speed profile; Shodan attack surface (zero hits noted explicitly); operational pattern analysis; risk tier; confidence assessment per category (HIGH/MEDIUM/LOW/SPECULATIVE); source cross-reference table.
- *red-team-playbook.md*: attack vectors by vessel type (USB drop, AIS spoofing, cellular MiTM, VSAT compromise); step-by-step execution with equipment and cost; M-SOC detection points; integrated kill chain; success criteria.
- *indicators-and-detection.md*: indicator table (ID, type, phase, priority); Elastic SIEM rules (EQL/threshold/query); Zeek scripts; Wazuh/Osquery rules; Grafana alerts; M-SOC runbook.
- *methodology-appendix.md*: time per phase; tool-call breakdown by type with success/failure/retry; sources queried; complete Shodan query catalog; data volume; failed/retried operations.

---

## Confidence Protocol

Confidence is assigned per finding category using a tiered adaptation of structured analytic tradecraft:

| Tier | Condition |
|---|---|
| **HIGH** | 3+ independent sources confirm the same value |
| **MEDIUM** | 2 independent sources |
| **LOW** | single source or inference |
| **SPECULATIVE** | derived from indirect evidence only |

**Source independence:** different organizations, different collection methods, different time periods.

**Verification thresholds:**
- Critical claims: 3+ independent sources
- Important claims: 2+ independent sources
- Supporting claims: 1+ verifiable source

---

## Risk Tier Classification

Risk tier assignment is **rule-based and deterministic** (not LLM-dependent):

- **CRITICAL:** 5+ active sanctions regimes AND withdrawn IACS classification AND confirmed AIS dark operations AND no disclosed P&I insurance.
- **HIGH:** multiple sanctions regimes, or withdrawn classification with AIS dark periods, or vessels >20,000 GT on international passenger routes with exploitable IP exposure.
- **MEDIUM:** general cargo and container ships; single sanctions regime.
- **LOW:** pleasure craft with no detectable internet exposure.

---

## Reporting Standards

Every report must include:
1. **Executive summary** — key findings, risk assessment, recommendation
2. **Methodology** — sources consulted, tools used, collection timeline, limitations
3. **Findings by category** — with fact-vs-inference labelling, source citations, confidence levels
4. **Confidence assessment** — per-finding confidence, overall confidence, information gaps
5. **Caveats** — unverified claims, potential biases, currency of information

---

## Ethical Framework

Mandatory pre-checks for every investigation:
- **Explicit authorization** — written permission/engagement scope
- **Defined scope** — target, information types, purpose, boundaries documented
- **Legal compliance** — GDPR, applicable privacy and computer-misuse law, platform ToS
- **Proportionality** — collect only what is necessary for the stated purpose

**Always:** use only publicly available sources; document all sources; respect ToS; minimize collection; distinguish fact from inference; multiple-source verification; disclose limitations.

**Never:** access private systems without authorization; use pretexting/impersonation; social engineer targets; circumvent access controls; purchase illegally obtained data; exceed authorized scope.

**Data handling:** minimize to scope; document sources immediately; encrypt at rest; share on need-to-know basis; defined retention and secure destruction.

---

## References

- `references/methodology.md` — OSINT methodology, source hierarchy, quality gates
- `references/vessel-osint-report-template.md` — report deliverable structure
- `references/ethical-framework.md` — full ethical and legal framework
- `references/shodan-maritime-osint.md` — maritime-specific Shodan filters and query patterns
- `references/sources.md` — OSINT tools catalog from the OSINT Maritime Framework paper (IEEE Access 2026, Tables 1–6, 103 platforms, human-readable)
- `references/sources.json` — same catalog as structured JSON (103 platforms across 6 categories)
- `references/paper-sources.json` — **operational data sources used in the IEEE Access validation** (Equasis, Shodan, AIS chain, sanctions lists, OCCRP, MISP) — the source set that produced the 63-vessel findings
- OSINT Maritime Framework: Nasr et al., "A Proactive Defense: An Open-Source Intelligence (OSINT) Framework for Maritime Cybersecurity," IEEE Access, 2026. DOI 10.1109/ACCESS.2026.3673557
