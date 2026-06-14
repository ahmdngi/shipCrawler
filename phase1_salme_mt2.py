#!/usr/bin/env python3
"""MarineTraffic retry with different wait strategy"""
import json, re, time
from cloakbrowser import launch

MMSI = 276329000
URL = f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{MMSI}"

browser = launch(headless=True, timeout=60000)
page = browser.new_page()
try:
    page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
    time.sleep(3)
    text = page.inner_text("body")
    html = page.content()
except Exception as e:
    print(f"[!] Error: {e}")
    text = ""
    html = ""
finally:
    browser.close()

for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
    try:
        j = json.loads(m.group(1))
        items = j if isinstance(j, list) else [j]
        for item in items:
            if isinstance(item, dict) and "latitude" in item:
                print("\n### JSON-LD")
                print(json.dumps(item, indent=2))
    except:
        pass

for pat in [r'"lat":\s*([\d.-]+),\s*"lng":\s*([\d.-]+)', r'"latitude":\s*([\d.-]+),\s*"longitude":\s*([\d.-]+)']:
    m = re.search(pat, html)
    if m:
        print(f"\n### Position: Lat {m.group(1)}, Lon {m.group(2)}")
        break

print("\n### Text (first 3000)")
print(text[:3000])
