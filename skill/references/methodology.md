# OSINT Methodology

## Core Principles

### 1. Intelligence Cycle

```
Planning → Collection → Processing → Analysis → Dissemination
   ↑                                                       │
   └───────────────────────────────────────────────────────┘
```

- **Planning:** Define objectives, scope, requirements
- **Collection:** Gather raw data from sources
- **Processing:** Organize and format collected data
- **Analysis:** Extract meaning, identify patterns
- **Dissemination:** Report findings to stakeholders

### 2. Source Hierarchy

| Tier | Type | Examples |
|------|------|----------|
| **1** | Primary Sources | SEC, SoS, USPTO, PACER & state courts, Government databases, Company official filings |
| **2** | Verified Secondary | Established news, academic pubs, industry reports, Crunchbase, LinkedIn |
| **3** | Community/Social | Social media profiles, forums, review sites, crowdsourced data |
| **4** | Technical | DNS records, WHOIS, certificate transparency, Shodan/Censys |

### 3. Multi-Source Verification

**Minimum thresholds:**
- Critical claims: 3+ independent sources
- Important claims: 2+ independent sources
- Supporting claims: 1+ verifiable source

**Independence criteria:** Different organizations, different collection methods, different time periods.

## Collection Methodology

### Technical vs. Research Split

- **Technical tools for:** DNS enumeration, IP geolocation, certificate analysis, port scanning (authorized), WHOIS lookups.
- **Research agents for:** Business intelligence, reputation research, threat intelligence, historical analysis, verification.

## Analysis Framework

### Confidence Levels

- **HIGH (80-100%):** Multiple independent confirmations, official source, direct observation, no contradicting evidence
- **MEDIUM (50-79%):** Some supporting evidence, limited independent confirmation, credible single source, minor contradictions explained
- **LOW (20-49%):** Single unverified source, circumstantial evidence, significant gaps, some contradictions
- **SPECULATIVE (<20%):** Inference only, no direct evidence, conflicting info, pattern matching without confirmation

### Red Flag Classification

| Level | Examples |
|-------|----------|
| **CRITICAL** (Investigation blocker) | Fraud indicators, regulatory violations, misrepresentation of material facts, criminal activity |
| **HIGH** (Significant concern) | Missing registrations, unverifiable claims, transparency failures, past regulatory issues |
| **MEDIUM** (Worth noting) | Minor discrepancies, limited online presence, industry concerns, competitive weaknesses |
| **LOW** (Monitor only) | Minor gaps, normal business risks, industry-standard issues |

## Domain-First Protocol

For Company OSINT, domain discovery is **BLOCKING**.

1. Execute ALL 7 enumeration techniques:
   - Certificate Transparency (crt.sh)
   - DNS enumeration
   - Search engine discovery
   - Social media link extraction
   - Business registration website fields
   - WHOIS reverse lookups
   - Related TLD checking

2. **Quality Gate:** 95%+ confidence before proceeding.

3. Categorize discovered domains: Primary website, Investor portals, Marketing/campaign sites, Product portals, Email domains, Development/staging.

4. Document gaps and confidence level.

**Why this matters:** Prevents missing investor-facing portals on alternative TLDs (.partners, .capital, .fund).

## Quality Gates

**Before moving to next phase:**
- [ ] All required techniques executed
- [ ] Confidence threshold met
- [ ] Gaps documented
- [ ] Red flags noted
- [ ] Verification complete

**If quality gate fails:**
1. Document gaps
2. Run additional collection
3. Re-assess confidence
4. Proceed only when threshold met OR document limitations and proceed with caveats.

## Reporting Standards

### Required Elements

1. **Executive Summary** — Key findings, risk assessment, recommendation
2. **Methodology** — Sources consulted, tools used, collection timeline, limitations
3. **Findings by Category** — Business/entity info, technical infrastructure, reputation/media, risk factors
4. **Confidence Assessment** — Per-finding confidence, overall confidence, information gaps
5. **Recommendations** — Next steps, follow-up investigation, mitigation actions
