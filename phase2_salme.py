#!/usr/bin/env python3
"""Shipcrawler Phase 2 — Attack Surface Discovery via Shodan for SALME"""

import json, shodan, sys, time, os

# Read API key from file
key_paths = [
    os.path.expanduser("~/.shodan/api_key"),
    os.path.expanduser("~/.config/shodan/api_key"),
]
key = os.environ.get("SHODAN_API_KEY")
if not key:
    for p in key_paths:
        if os.path.exists(p):
            with open(p) as f:
                key = f.read().strip()
            break

if not key:
    print("ERROR: No Shodan API key found")
    sys.exit(1)

api = shodan.Shodan(key)
acct = api.info()
print(f"Shodan account: {acct.get('plan','?')}, credits used: {acct.get('query_credits',0)}")
plan_name = acct.get('plan', 'unknown').lower() if isinstance(acct.get('plan'), str) else str(acct.get('plan', 'unknown')).lower()

results = {
    "vessel": "SALME",
    "imo": 7431337,
    "mmsi": 276329000,
    "phase": "Phase 2 — Attack Surface Discovery",
    "account_plan": plan_name,
    "searches": {}
}

def safe_search(label, query, **kwargs):
    print(f"\n=== SEARCH: {label} ===")
    print(f"Query: {query}")
    try:
        resp = api.search(query, **kwargs)
        total = resp.get('total', 0)
        matches = resp.get('matches', [])
        print(f"Total results: {total}")
        for m in matches[:8]:
            ip = m.get('ip_str', '?')
            port = m.get('port', '?')
            org = m.get('org', '?')
            hostnames = ', '.join(m.get('hostnames', []) or ['-'])
            product = m.get('product', '?')
            data_preview = m.get('data', '')[:120].replace('\n', ' ')
            print(f"  IP:{ip}:{port} | {product} | {org} | {hostnames[:50]}")
            print(f"    {data_preview}")
        results["searches"][label] = {
            "query": query,
            "total": total,
            "matches": [{k: m.get(k) for k in ['ip_str','port','org','hostnames','product','transport','city','country_name','os']} for m in matches[:15]]
        }
        return resp
    except shodan.exception.APIError as e:
        print(f"  ERROR: {e}")
        results["searches"][label] = {"query": query, "error": str(e)}
        return None

# ========== DIRECT VESSEL NAME SEARCHES ==========
print("=" * 70)
print("PHASE 2: ATTACK SURFACE DISCOVERY — SALME")
print("=" * 70)
safe_search("Vessel name 'SALME'", "SALME vessel")
safe_search("Vessel name + ship", "SALME ship")
safe_search("Vessel name exact phrase", '"SALME" vessel')
safe_search("SALME research vessel", '"SALME" research')
safe_search("SALME Estonian ship", '"SALME" Estonia ship')

# ========== IDENTIFIER SEARCHES ==========
print("\n" + "=" * 70)
print("IDENTIFIER SEARCHES")
print("=" * 70)
safe_search("MMSI 276329000", "276329000")
safe_search("MMSI without prefix", "76329000")
safe_search("IMO 7431337", "7431337")
safe_search("Call sign ES2408", "ES2408")

# ========== MARITIME PROTOCOL ENUMERATION ==========
print("\n" + "=" * 70)
print("MARITIME PROTOCOL ENUMERATION")
print("=" * 70)
safe_search("Signal K servers", "Signal K port:3000", limit=10)
safe_search("signalk HTTP", "signalk HTTP", limit=10)
safe_search("SAILOR 900 VSAT", "SAILOR 900 cobham VSAT", limit=5)
safe_search("Allegro-WebServer (SAILOR)", "Allegro-WebServer", limit=10)
safe_search("NMEA 0183/2000", "NMEA 0183 NMEA 2000", limit=10)
safe_search("AIS receivers (dump1090)", "AIS dump1090 rtl-sdr", limit=5)
safe_search("ECDIS navigation systems", "ECDIS chart navigation", limit=10)
safe_search("Maritime bridge cameras", "vessel bridge navigation camera", limit=10)

# ========== ESTONIA-SPECIFIC ==========
print("\n" + "=" * 70)
print("ESTONIA-SPECIFIC RECONNAISSANCE")
print("=" * 70)
safe_search("Estonia port 3000 (Signal K)", "country:EE port:3000", limit=10)
safe_search("Estonia research vessels", "country:EE research vessel", limit=10)
safe_search("Estonia maritime systems", "country:EE maritime", limit=10)
safe_search("Estonia navigation/chart", "country:EE navigation", limit=10)

# ========== GULF OF FINLAND / BALTIC SEA ==========
print("\n" + "=" * 70)
print("REGIONAL: GULF OF FINLAND / BALTIC SEA")
print("=" * 70)
safe_search("Gulf of Finland maritime", '"Gulf of Finland" maritime', limit=10)
safe_search("Gulf of Finland vessel", '"Gulf of Finland" vessel', limit=10)
safe_search("Tallinn maritime systems", "Tallinn maritime", limit=10)

# ========== TALTECH / TALLINN UNIVERSITY RELATED ==========
print("\n" + "=" * 70)
print("TALTECH / TALLINN UNIVERSITY OF TECHNOLOGY")
print("=" * 70)
safe_search("TalTech network", "taltech.ee", limit=10)
safe_search("Tallinn University of Technology", '"Tallinn University of Technology"', limit=5)

# Check if any IPs were found that need deep inspection
all_ips = set()
for label, data in results["searches"].items():
    if "matches" in data:
        for m in data["matches"]:
            ip = m.get("ip_str")
            if ip:
                all_ips.add(ip)

if all_ips:
    print(f"\n\nDiscovered IPs: {', '.join(sorted(all_ips))}")
    print("Running host intelligence on each...")
    for ip in sorted(all_ips):
        safe_host(ip)
else:
    print("\n\nNo IPs discovered from searches — no host intelligence to run.")

# ========== STATISTICS ==========
print("\n" + "=" * 70)
print("GLOBAL STATISTICS")
print("=" * 70)
for label, query in [
    ("Signal K servers (global)", "Signal K port:3000"),
    ("signalk HTTP (global)", "signalk HTTP"),
    ("SAILOR 900 VSAT (global)", "SAILOR 900 cobham VSAT"),
    ("Allegro-WebServer (global)", "Allegro-WebServer"),
    ("ECDIS systems (global)", "ECDIS chart navigation"),
    ("Maritime systems in Estonia", "country:EE maritime"),
    ("Port 3000 in Estonia", "country:EE port:3000"),
]:
    try:
        c = api.count(query)
        print(f"  {label}: {c.get('total',0)}")
        results.setdefault("statistics", {})[label] = c.get('total', 0)
    except Exception as e:
        print(f"  {label}: ERROR {e}")
        results.setdefault("statistics", {})[label] = str(e)

# ========== SAVE ==========
with open("/root/shipcrawler-v4/phase2_salme_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to /root/shipcrawler-v4/phase2_salme_results.json")
print("DONE")
