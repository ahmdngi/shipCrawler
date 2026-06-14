#!/usr/bin/env python3
"""Fetch longer port history from VesselFinder's track page"""
import json, re, time
from cloakbrowser import launch

MMSI = 276329000

# Try the track/port calls URL
for label, url in [
    ("VesselFinder details", f"https://www.vesselfinder.com/vessels/details/{MMSI}"),
    ("FleetMon", f"https://www.fleetmon.com/vessels/SALME_{MMSI}"),
]:
    print(f"\n=== {label} ===")
    try:
        browser = launch(headless=True, timeout=45000)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=40_000)
        time.sleep(2)
        page.wait_for_load_state("networkidle", timeout=10_000)
        text = page.inner_text("body")
        browser.close()
        print(text[:3000])
    except Exception as e:
        browser.close()
        print(f"[!] Error: {e}")
