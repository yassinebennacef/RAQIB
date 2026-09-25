"""Browser smoke test of the web app (Playwright, drives the installed Edge or Chromium).

Usage (server running):  .venv/Scripts/python tests/e2e/smoke_ui.py [--url http://127.0.0.1:8000]
Visits every page, plays replay days, opens the inspector, logs a decision, scores a preset,
saves screenshots to docs/screenshots/ and exits 1 on any console error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def launch(p):
    for channel in ("msedge", "chrome", None):
        try:
            return p.chromium.launch(channel=channel) if channel else p.chromium.launch()
        except Exception:  # noqa: BLE001 - try the next browser
            continue
    raise RuntimeError("No browser found: install Edge/Chrome or run `playwright install chromium`")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--shots", default=str(ROOT / "docs" / "screenshots"))
    args = ap.parse_args()
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        # 1. Control room: play ~10 days
        page.goto(args.url + "/")
        page.wait_for_selector("text=Same inspections, more fraud found", timeout=20000)
        page.wait_for_selector("text=Today's declarations")
        page.wait_for_timeout(800)
        page.screenshot(path=str(shots / "01_control_room_start.png"))
        page.get_by_label("Replay speed").fill("8")
        page.get_by_role("button", name="Play").click()
        page.wait_for_timeout(1400)  # ~10 days at 8 days/s
        page.get_by_role("button", name="Pause").click()
        page.wait_for_timeout(700)
        page.screenshot(path=str(shots / "02_control_room_replay.png"))
        page.get_by_role("button", name="Skip to the end").click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "03_control_room_end.png"))

        # 2. Inspector from the feed
        page.locator("main ul li button").first.click()
        page.wait_for_selector("text=Why this risk", timeout=15000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "04_inspector.png"), full_page=True)
        page.get_by_role("button", name="Inspect", exact=True).click()
        page.wait_for_selector("text=Decision logged", timeout=10000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / "05_inspector_decision.png"))

        # 3. Try a declaration with a preset
        page.goto(args.url + "/score")
        page.get_by_role("button", name="Public-safety alert").click()
        page.wait_for_selector("text=Public-safety signals", timeout=15000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "06_try_declaration.png"), full_page=True)

        # 4. Model lab
        page.goto(args.url + "/lab")
        page.wait_for_selector("text=Data & honest limits", timeout=15000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(shots / "07_model_lab.png"), full_page=True)

        # 5. About
        page.goto(args.url + "/about")
        page.wait_for_selector("text=The method in 6 steps", timeout=15000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(shots / "08_about.png"), full_page=True)

        # 6. Laptop resolution
        small = browser.new_page(viewport={"width": 1366, "height": 768})
        small.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        small.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        small.goto(args.url + "/")
        small.wait_for_selector("text=Same inspections, more fraud found", timeout=20000)
        small.get_by_role("button", name="Skip to the end").click()
        small.wait_for_timeout(1200)
        small.screenshot(path=str(shots / "09_control_room_1366.png"))
        browser.close()

    if errors:
        print("FAIL - console errors:")
        for e in errors:
            print("  ", e)
        return 1
    print(f"OK - all pages rendered without console errors; screenshots in {shots}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
