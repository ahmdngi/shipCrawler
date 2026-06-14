#!/usr/bin/env python3
"""Phase 1 — Target Identification: SALME (IMO 7431337, MMSI 276329000)"""
import json, sys, re, time
from cloakbrowser import launch

MMSI = 276329000
URL = f"https://www.vesselfinder.com/vessels/details/{MMSI}"

print(f"[*] Launching CloakBrowser (headless) for {URL}...")
browser = launch(headless=True, timeout=60000)
page = browser.new_page()

try:
    page.goto(URL, wait_until="networkidle", timeout=60_000)
    time.sleep(2)
    html = page.content()
    text = page.inner_text("body")
except Exception as e:
    print(f"[!] Page load error: {e}")
    html = ""
    text = ""
finally:
    browser.close()

# --- Parse vessel name from page ---
title_match = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
title = title_match.group(1).strip() if title_match else ""
print(f"[*] Page title: {title}")

# --- Extract JSON-LD ---
for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
    try:
        j = json.loads(m.group(1))
        items = j if isinstance(j, list) else [j]
        for item in items:
            if isinstance(item, dict) and "latitude" in item:
                print("\n### JSON-LD Data")
                print(json.dumps(item, indent=2))
    except:
        pass

# --- Position from JS ---
lat_lng = None
for m in re.finditer(r'"lat":\s*([\d.-]+),\s*"lng":\s*([\d.-]+)', html):
    lat_lng = (float(m.group(1)), float(m.group(2)))
    break
if not lat_lng:
    for m in re.finditer(r'"latitude":\s*([\d.-]+),\s*"longitude":\s*([\d.-]+)', html):
        lat_lng = (float(m.group(1)), float(m.group(2)))
        break
if lat_lng:
    print(f"\n### Position (JS): Lat {lat_lng[0]}, Lon {lat_lng[1]}")

# --- Detail table ---
rows = re.findall(r'<td class="n3">(.*?)</td>\s*<td>(.*?)</td>', html, re.DOTALL)
print("\n### Detail Table")
for label, val in rows:
    v = re.sub(r'<.*?>', '', val).strip().replace('\u00a0', '').strip()
    l = re.sub(r'<.*?>', '', label).strip()
    if v:
        print(f"  {l}: {v}")

# --- Full text (first 5000) ---
print("\n### Page Text (trimmed)")
print(text[:5000])
