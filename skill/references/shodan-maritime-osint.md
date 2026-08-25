# Shodan Maritime OSINT Playbook

Complete Shodan workflow for vessel attack-surface discovery. Load this
reference when a ShipCrawler investigation reaches Phase 2 (Attack Surface)
or Phase 3 (Vulnerability Assessment), or when the user asks for Shodan
queries, VSAT exposure checks, or exposed maritime equipment hunting.

Companion file: `shodan-setup.md` (install + API key + rate limits).
The SKILL.md "Shodan Integration" section holds the raw API command set —
this file is the maritime-specific playbook on top of it.

Source: official Shodan book (book.shodan.io) — getting-started, developer
APIs, command-line tools, behind-the-scenes sections.

## 0. Query Syntax Fundamentals

**Critical gotcha: by default Shodan only searches the banner `data`
property.** Searching `SingTel Mobile` as plain text won't find orgs —
you must use filters for non-data properties.

- Filter format: `filtername:value` — **no space** between name and value.
- Values with spaces must be quoted: `org:"SingTel Mobile"`.
- Filters combine with implicit AND: `org:"SingTel Mobile" city:Singapore`.
- All filters accept comma-separated values, OR-ed:
  `product:MySQL,PostgreSQL`
- Numeric filters support ranges: `port:>1024,<6000` (exclusive bounds)
- Default full-text search hits the `data` property (the raw service banner).

Filter reference: https://www.shodan.io/search/filters · examples:
https://www.shodan.io/search/examples

## 0.5 Free APIs (no API key required)

These three are keyless and cost zero query credits — use them first for
bulk work before spending credits on the main API.

### InternetDB (https://internetdb.shodan.io/{IP})

Bulk IP lookup, no key, bursts up to 10,000 req/s. DB updated weekly
(Sunday midnight UTC). Response: ports, cpes, hostnames (reverse DNS +
cert info), tags, vulns (verified + unverified):

```bash
curl https://internetdb.shodan.io/51.83.59.99 | jq
# {"ip": "...", "ports": [22,80,443,500], "cpes": ["cpe:/a:f5:nginx"],
#  "hostnames": ["..."], "tags": ["vpn"], "vulns": ["CVE-2017-15906"]}
```

Use for: cheap fleet-scale sweep — enumerate a VSAT provider's IP block or
a list of candidate IPs and see which have open ports/vulns **without
touching query credits**.

### CVEDB (https://cvedb.shodan.io/cve/{CVE_ID})

Fast CVE lookup, no key, NVD-sourced, updated daily. Returns CVSS v2/v3,
EPSS + ranking, CISA KEV flag, references, CPEs:

```bash
curl https://cvedb.shodan.io/cve/CVE-2025-8960 | jq
# {"cve_id": "...", "cvss": 7.3, "cvss_v2": 7.5, "cvss_v3": 7.3,
#  "epss": 0.00032, "ranking_epss": 0.07151, "kev": false,
#  "references": [...], "published_time": "...", "cpes": [...]}
```

Use for: Phase 3 — enrich each CVE found on a host with EPSS likelihood +
KEV status instead of `api.exploits.search()` (which costs credits).

### Certificate Transparency Log (https://ctl.shodan.io)

Search CT logs by domain or cert SHA-256. Useful for mapping a target's
attack surface and tracking cert issuance:

- `GET /api/v1/domain/{domain}` — certificates matching a domain
- `GET /api/v1/domain/{domain}/hostnames` — all hostnames ever in CT logs
- `GET /api/v1/cert/{sha256}` — certificate for a hash

```python
import requests
hostnames = requests.get("https://ctl.shodan.io/api/v1/domain/shodan.io/hostnames").json()
```

Record fields: hash, subject_cn, issuer_cn, not_before/not_after (Unix
epoch seconds), san_dns_names. Use for: discovering hidden subdomains of a
shipping company / VSAT provider / port authority.

### Geonet (https://geonet.shodan.io)

DNS lookups and pings from multiple global locations. Detects
location-based load balancing and measures latency:

```bash
curl https://geonet.shodan.io/api/geoping/74.6.231.20 | jq
# per-location: {ip, is_alive, min_rtt, avg_rtt, max_rtt, rtts,
#               packets_sent, packets_received, packet_loss, from_loc:{city,country,latlon}}
```

Use for: verifying a discovered maritime service is globally reachable and
not geo-restricted; latency baseline before a scan.

## 0.6 Keyless CLI Tools

### nrich (bulk IP enrichment → InternetDB)

Analyzes all IPs in a file (or stdin) for open ports/vulns. No Shodan
account needed. Great for data pipelines and fleet-scale sweeps:

```bash
wget https://gitlab.com/api/v4/projects/33695681/packages/generic/nrich/latest/nrich_latest_x86_64.deb
sudo dpkg -i nrich_latest_x86_64.deb
nrich < ips.txt   # or: cat ips.txt | nrich
# 5.196.94.201 (...) Ports: 443 Tags: eol-product CPEs: cpe:/a:f5:nginx:1.22.1
```

### shodan-hash (favicon hashing, no account)

Computes Shodan's favicon hash for a URL, local file, or text — then use
`http.favicon.hash:<hash>` as a search filter to find all sites sharing
that favicon (classic org-fingerprinting technique):

```bash
shodan-hash url https://example.com    # → hash value
# then: api.search('http.favicon.hash:-1825064917')
```

## 1. Vessel-Focused Workflow (one vessel)

For a specific vessel (have IMO / MMSI / name / call sign):

```python
import shodan, json
api = shodan.Shodan(open('/root/.shodan/api_key').read().strip())

targets = {
    "name": "BOREALIS",
    "mmsi": "311000987",
    "imo": "9122552",
    "callsign": "V2FO8",
}

# Step 1 — find any Shodan fingerprint mentioning the vessel identity
for field, value in targets.items():
    for q in [f'"{value}"', f'{value}', f'{value} vessel', f'{value} ship']:
        try:
            r = api.search(q, limit=20)
            if r["total"] > 0:
                print(f"=== {field}: {value} → {r['total']} hits ===")
                for m in r["matches"]:
                    print(json.dumps({
                        "ip": m.get("ip_str"), "port": m.get("port"),
                        "org": m.get("org"), "os": m.get("os"),
                        "hostnames": m.get("hostnames"),
                        "title": (m.get("http") or {}).get("title"),
                        "server": (m.get("http") or {}).get("server"),
                        "data_head": (m.get("data") or "")[:200],
                    }, indent=2))
        except shodan.APIError as e:
            if "rate" in str(e).lower():
                print("RATE LIMITED — wait 60s"); break

# Step 2 — deep host lookup on any IPs found (ports, banners, CVEs)
# api.host('<IP>', history=True, minify=False)

# Step 3 — check IP range of the vessel's VSAT provider if known
# api.search('org:"<VSAT-ISP>" country:<flag-state>')
```

**Pagination & history (official):**
- `api.search(q, page=2)` — explicit page; each page holds up to 100 results.
- `api.search_cursor(q)` — generator over all results, use when iterating
  everything.
- `api.host(ip, history=True)` — historical banners up to **90 days old**;
  default returns only the most recent collection.
- Shodan crawls the Internet at least weekly; monitored assets at least daily.

**Reality check for vessels:** most ships show **zero Shodan footprint** —
satcom links are NAT'd behind the VSAT provider and AIS/ECDIS gear is on
isolated LANs. Zero hits is a *valid finding* (good cyber hygiene / no
direct internet exposure), not a failure. Document it as such in the
analyst report. See ShipCrawler IEEE Access 2026 — zero-footprint across
the 63-vessel cohort was the norm.

## 2. Maritime Equipment Fingerprint Catalog

Search strings that reliably surface maritime OT on Shodan. Each is a
`api.search(q, limit=...)` call; add `country:XX`, `port:NNNN`, `org:"..."`
filters to narrow.

### VSAT / Satcom terminals
```python
queries = [
    'SAILOR 900 COBHAM VSAT',          # Cobham SAILOR 900
    'SAILOR XTR',                      # SAILOR XTR Ku-band
    'Allegro-WebServer',               # SAILOR 900 web UI
    'KVH TracPhone',                   # KVH TracPhone V3/V7
    'KVH TracVision',                  # KVH TV antennas
    'Intellian',                       # Intellian VSAT
    'JRC JUE',                         # JRC satcom
    'Furuno Felcom',                   # Furuno satcom
    'iDirect',                         # iDirect VSAT modems (huge marine install base)
    'Hughes HN',                       # Hughes VSAT modems
    'Linkway',                         # older satcom modem line
]
```

### AIS / navigation / bridge systems
```python
queries = [
    'Signal K port:3000',              # Signal K servers (maritime data hub)
    'signalk HTTP',
    'NMEA 0183 NMEA 2000',             # NMEA gateways
    'NMEA 2000 gateway',
    'AIS transponder',                 # AIS units
    'AIS base station',
    'AIS dump1090 rtl-sdr',            # hobbyist AIS receivers (mismatch check)
    'ECDIS chart navigation',          # ECDIS workstations
    'ECDIS',                           # broad
    'Raytheon marine',                 # bridge electronics (Raytheon/Anschütz)
    'Anschütz',                        # Anschütz gyro/ECDIS
    'Furuno network',                  # Furuno bridge network gear
    'Wärtsilä', 'Wartsila',            # propulsion/automation
    'Danfoss',                         # marine drives/automation (also industrial)
    'Kongsberg',                       # Kongsberg maritime (also offshore/industrial)
    'bridge navigation camera',        # exposed webcams
]
```

### Fleet / vessel-management software
```python
queries = [
    'vessel tracking ship fleet',
    'maritime ship vessel fleet',
    'fleet management ship',
    'voyage data recorder',
    'AtoN',                            # aids to navigation (buoys, beacons)
]
```

### Regional scoping examples
```python
api.search('Signal K country:EE')
api.search('SAILOR country:FI')
api.search('port:3000 country:EE signalk')
api.search('org:"Telia" country:EE')   # ISP-scoped
api.search('port:8080 ECDIS')
```

## 3. Ports of Interest

| Port | Typical maritime service |
|------|--------------------------|
| 3000 | Signal K, Grafana, misc dev UIs |
| 8080 | VSAT/web admin consoles |
| 443 | HTTPS admin (SAILOR, KVH) |
| 80 | HTTP admin / webcams |
| 22 | SSH (maintenance backdoors) |
| 5900/5901 | VNC (chart PC / automation) |
| 3389 | RDP (shore-side or bridge PCs) |
| 2323 | Telnet on some OT gear |
| 5000/5001 | misc camera/automation UIs |
| 161 | SNMP (network gear, UPS) |
| 502 | Modbus (if any industrial control exposed) |

Use facets for a cheap stats pass (1 credit, no full results):

```python
r = api.search('Signal K', limit=1, facets=[('port', 10), ('country', 10), ('org', 10)])
print(r['facets'])
```

## 4. Vulnerability Assessment (Phase 3 hook)

For each discovered IP with services:

```python
host = api.host('<IP>', history=True, minify=False)
# host['vulns'] → {CVE-2024-xxxx: {cvss, epss, summary, references}}
# host['data']  → banner per port
# host['ssl']   → cert chain (issuer, subject, expiry) — check expired/self-signed

# Exploit DB check
api.exploits.search('SAILOR OR KVH OR signalk', limit=10)
```

Assessment notes:
- **Expired/self-signed SSL on satcom admin = red flag** — no patching discipline.
- **Default creds** — check known defaults per vendor (SAILOR admin/admin, KVH, etc.)
  *documented in analyst report only*, never test against non-target systems
  (MHV NDA / scope discipline applies).
- **CVE mapping** — map banner versions (e.g., Apache 2.4.49 → CVE-2021-41773,
  iDirect versions) into the playbook risk table.

## 5. Detection / Monitoring (M-SOC feed)

Shodan network alerts on ranges you care about:

```python
# List existing
api.alerts()

# Monitor a VSAT provider block or own vessel IPs
api.create_alert('vessel-fleet', '<IP>/32,<IP>/32')

# Check alert contents
api.alert_info('<ALERT_ID>')

# Optional notifier (email/slack) — api.notifiers()
```

Also usable for **continuous fleet monitoring**: alert on new ports/CVEs
appearing on the fleet's egress IPs.

## 6. Credit Budgeting (official model)

There are **3 credit types**, varying by API plan:

- **Query credits** — used by `/shodan/host/search` (search) and
  `/dns/domain/{domain}` (domain lookup). **1 query credit per 100 pages
  of search results** (each page = up to 100 results, so 1 credit ≈ up to
  10,000 banner results) or per page of domain info. **IP lookups
  (`api.host()`) do NOT consume query credits.**
- **Scan credits** — on-demand scanning (`api.scan()`): 1 credit per host
  scanned per month.
- **Alert credits** — Shodan Monitor: 1 credit per monitored IP.

So on the dev plan (100 query credits):
- **Search = 1 credit per 100 pages** — not per call. A normal vessel
  investigation (a handful of searches, facets, pages) costs ~1-3 credits,
  not 10-15. Batch aggressively.
- **Facets on a search = still covered by the same query credit.**
- **`api.count()`** — cheap existence check, no result bodies.
- **IP host lookups are FREE** — `api.host(ip, history=True)` doesn't touch
  query credits. Use host lookups liberally on every IP a search surfaces.
- **`api.scan()`** — consumes scan credits; only use on assets you own or
  have authorization for.
- **Keyless APIs (InternetDB/CVEDB/CT/Geonet) cost nothing** — prefer them
  for bulk enrichment (see §0.5).

## 7. Pitfalls

- **Rate limiting:** `APIError` with "rate" → back off 60s. Free tier is
  brutal on bursty loops — put sleeps between query variants.
- **Zero footprint is normal for vessels** — report it, don't chase it.
- **Vessel name collisions** — generic names (BOREALIS, MARIA) hit unrelated
  servers. Always cross-check hits with MMSI/IMO/callsign strings before
  attributing to the vessel.
- **Don't attribute ports to the ship hull** — exposed services are usually
  shore offices, agents, or VSAT provider gear with the same name in banners.
- **`shodan` CLI broken in Hermes venv** (`pkg_resources` error) — use the
  Python API directly; key at `~/.shodan/api_key` (root) or `SHODAN_API_KEY` env.
- **Quota check:** `api.info()` before big batch runs — if `query_credits`
  is near zero, defer non-critical searches.
