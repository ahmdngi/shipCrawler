# Vessel OSINT Report — Template

**Classification:** Internal — M-SOC Use Only
**Date:** <YYYY-MM-DD>
**Analyst:** <Name>
**Framework:** OSINT Maritime Framework (Nasr et al., IEEE Access 2026)

## Deliverable Structure

```
<vessel-name>-report/
├── README.md                   # Report index with contents table and key finding
├── analyst-report.md           # Full OSINT findings
├── red-team-playbook.md        # Attack scenario design
└── indicators-and-detection.md # M-SOC detection configuration
```

---

## analyst-report.md — Skeleton

```
# <VESSEL NAME> — Full OSINT Analyst Report

**Vessel:** <NAME>
**MMSI:** <MMSI>
**Call Sign:** <CALL SIGN>
**IMO:** <IMO or "None (pleasure craft — not assigned)">
**Flag:** <COUNTRY>
**Type:** <TYPE>
**Transponder:** AIS Class A/B
**Last Updated:** <TIMESTAMP UTC>

---

## 1. Vessel Specifications

| Parameter | Value |
|-----------|-------|
| Length (LOA) | <X> m |
| Beam (Width) | <X> m |
| Max Draught | <X> m |
| DWT | <X> or "Not available (pleasure craft)" |
| Year Built | <YEAR or "Not publicly listed"> |
| Port of Registry | <PORT or "Not publicly listed"> |
| Owner/Operator | <NAME or "Not publicly available"> |

## 2. Current Status

- **Navigational Status:** <status>
- **Position:** ~<lat>, <lon>
- **Location:** <location>
- **Speed:** <X.X> kn
- **Course/Heading:** <COG>/<HDG>
- **Destination:** <DEST> (reported via AIS)
- **Draught (current):** <X.X> m

## 3. Recent Port Call History

| Date | Port | Duration | Notes |
|------|------|----------|-------|
| <DATE> | <PORT> | <TIME> | <CONTEXT> |

### Speed Profile (Last 24h)
- **Average:** <X.X> kn
- **Max:** <X.X> kn

## 4. Internet Attack Surface (Shodan)

| Query | Results |
|-------|---------|
| `<NAME>` (vessel name) | <N> matches |
| `<MMSI>` (MMSI) | <N> matches |
| Port filters (if applicable) | <N> matches |

**Assessment:** <summary of findings — note 0 hits explicitly as a finding>

## 5. Operational Pattern Analysis

**Home zone:** <area>
**Recurring pattern:** <description>

## 6. Classification & Risk Triggers

**Risk Tier:** HIGH / MEDIUM / LOW / NEGLIGIBLE
<brief rationale based on attack surface findings>

## 7. Confidence Assessment

| Category | Confidence | Methodology |
|----------|-----------|-------------|
| Identity & specs | HIGH/MEDIUM/LOW | <source count and method> |

## 8. Source Cross-Reference

| Source | Vessel ID | Data Matched |
|--------|-----------|-------------|
| MarineTraffic | <shipid> | <scope> |

---

*Report generated <DATE> using Shipcrawler (OSINT Maritime Framework, IEEE Access 2026)*
```

---

## red-team-playbook.md — Skeleton

```
# Red-Team Playbook: "<NAME>"

**Target:** <port zone / infrastructure>
**Proxy Vessel:** <VESSEL NAME, MMSI, type>
**Primary Objective:** <goal>
**Secondary Objective:** <goal>
**Rules of Engagement:** <controls>

---

## Overview

<Context — kill chain principle, why this vessel is relevant>

## Vector A: <Vector Name>

**Difficulty:** LOW/MEDIUM/HIGH
**Cost:** ~$<amount>
**Detection probability (without tuning):** LOW/MEDIUM/HIGH

### Equipment
| Item | Purpose |
|------|---------|

### Execution
```
Step 1: ...
Step 2: ...
```

### M-SOC Detection Points
| Detection Point | Expected Signal | Tool |
|----------------|---------------|------|

## Vector B: ...

## Integrated Kill Chain
```
Day 1–7:  Reconnaissance
Day 8:    Initial access via ...
```

## Success Criteria
| Criterion | Target | Measurement |
|-----------|--------|-------------|

---

*Playbook designed using Shipcrawler methodology (OSINT Maritime Framework, IEEE Access 2026)*
```

---

## indicators-and-detection.md — Skeleton

```
# Indicators & Detection Rules — <NAME>

**Target Stack:** Elastic SIEM, Zeek, Wazuh, PacketFence, Grafana

## 1. Indicator Table

| ID | Indicator | Type | Phase | Priority |
|----|-----------|------|-------|----------|
| I-001 | <description> | <network/hardware/auth> | <kill chain phase> | CRITICAL/HIGH/MEDIUM |

## 2. Elastic SIEM Detection Rules
```yaml
name: "<Rule Name>"
index: "<ES index pattern>"
type: "eql|threshold|query"
query: "..."
```

## 3. Zeek Scripts
<Code listings for AIS-radar correlation, C2 beacon detection, etc.>

## 4. Wazuh / Osquery Rules
<XML or config blocks>

## 5. Grafana Alert Rules
<JSON alert configurations>

## 6. M-SOC Runbook
### On <Alert Type>:
1. Triage: ...
2. Cross-reference: ...
3. Response actions: ...
4. Log to: ...

---

*Detection rules designed for the OSINT Maritime Framework M-SOC integration*
```
