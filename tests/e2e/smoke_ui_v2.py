"""Browser smoke test of the v2 web app (frontend-v2) - every route, no console errors.

Usage (server running with the v2 UI):  .venv/Scripts/python tests/e2e/smoke_ui_v2.py [--url http://127.0.0.1:8000]
Screenshots go to docs/screenshots/v2/.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def launch(p):
    for channel in ("msedge", "chrome", None):
        try:
            return p.chromium.launch(channel=channel) if channel else p.chromium.launch()
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("No browser found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--shots", default=str(ROOT / "docs" / "screenshots" / "v2"))
    ap.add_argument("--brief-wait", type=int, default=1500, help="ms to wait for the officer brief")
    ap.add_argument("--offline", action="store_true", help="block every request that does not go to --url (offline demo)")
    args = ap.parse_args()
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with urllib.request.urlopen(args.url + "/api/worklist?lane=RED&uncertain=false&page_size=1") as r:
        red_id = json.loads(r.read())["items"][0]["id"]

    blocked: list[str] = []

    def watch(page):
        if args.offline:
            def gate(route):
                if route.request.url.startswith(args.url):
                    route.continue_()
                else:
                    blocked.append(route.request.url)
                    route.abort()
            page.route("**/*", gate)
        page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        watch(page)

        page.goto(args.url + "/")
        page.wait_for_selector("text=Same inspections, more fraud found", timeout=20000)
        page.get_by_label("Replay speed").fill("8")
        page.get_by_role("button", name="Play").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Skip to the end").click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "01_control_room.png"))
        page.locator("main ul li button").first.click()
        page.wait_for_selector("text=Mini-inspector", timeout=10000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "02_control_room_sheet.png"))
        page.keyboard.press("Escape")

        page.goto(args.url + "/worklist")
        page.wait_for_selector("text=declarations", timeout=15000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "03_worklist.png"))
        page.get_by_label("Ask RAQIB in French, English or Arabic").fill("déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%")
        page.get_by_role("button", name="Understand").click()
        page.wait_for_selector("text=Apply filter", timeout=40000)
        page.screenshot(path=str(shots / "03b_ask_raqib_chips.png"))
        page.get_by_role("button", name="Apply filter").click()
        page.wait_for_selector("text=Ask RAQIB filter applied", timeout=15000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(shots / "03c_ask_raqib_applied.png"))
        page.locator("tbody tr").first.click()
        page.wait_for_selector("text=Open full inspector", timeout=15000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(shots / "04_worklist_sheet.png"))
        page.keyboard.press("Escape")

        page.goto(args.url + f"/declaration/{red_id}")
        page.wait_for_selector("text=exact waterfall", timeout=15000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(shots / "05_inspector.png"), full_page=True)
        page.get_by_role("tab", name="العربية").click()
        page.wait_for_selector("text=Regenerate", timeout=10000)
        page.wait_for_timeout(args.brief_wait)
        page.screenshot(path=str(shots / "05b_brief_ar.png"))
        page.get_by_role("button", name="Inspect", exact=True).click()
        page.wait_for_selector("text=Decision logged", timeout=10000)

        page.goto(args.url + "/score")
        page.get_by_role("button", name="Public-safety alert").click()
        page.wait_for_selector("text=What-if simulator", timeout=15000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(shots / "06_try_declaration.png"), full_page=True)

        page.goto(args.url + "/impact")
        page.wait_for_selector("text=Capacity curve", timeout=15000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(shots / "07_impact.png"), full_page=True)

        page.goto(args.url + "/explainability")
        page.wait_for_selector("text=Tested ideas", timeout=15000)
        page.wait_for_selector("text=What-if simulator", timeout=15000)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(shots / "08_explainability.png"), full_page=True)

        page.goto(args.url + "/lab")
        page.wait_for_selector("text=Data & honest limits", timeout=15000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(shots / "09_model_lab.png"), full_page=True)

        page.goto(args.url + "/model-card")
        page.wait_for_selector("text=Out-of-scope uses", timeout=15000)
        page.screenshot(path=str(shots / "10_model_card.png"), full_page=True)

        page.goto(args.url + "/journal")
        page.wait_for_selector("text=Chain intact", timeout=15000)
        page.screenshot(path=str(shots / "11_journal.png"))

        page.goto(args.url + "/about")
        page.wait_for_selector("text=The method in 6 steps", timeout=15000)
        page.screenshot(path=str(shots / "12_about.png"), full_page=True)

        # Assistant local Qwen3: one click from the sidebar, an example question lands in the worklist with chips
        page.goto(args.url + "/")
        page.get_by_role("link", name="Assistant (Qwen3 local)").click()
        page.wait_for_selector("text=État du modèle local", timeout=15000)
        page.screenshot(path=str(shots / "12b_assistant.png"), full_page=True)
        page.get_by_role("link", name="show uncertain cases from office 20").click()
        page.wait_for_selector("text=Apply filter", timeout=40000)
        page.get_by_role("button", name="Apply filter").click()
        page.wait_for_selector("text=Ask RAQIB filter applied", timeout=15000)

        # command palette + light theme
        page.goto(args.url + "/worklist")
        page.wait_for_selector("text=declarations", timeout=15000)
        page.keyboard.press("Control+k")
        page.keyboard.type("coffee")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "13_command_palette.png"))
        page.keyboard.press("Escape")
        page.evaluate("document.documentElement.classList.remove('dark'); document.documentElement.classList.add('light')")
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / "14_worklist_light.png"))

        small = browser.new_page(viewport={"width": 1366, "height": 768})
        watch(small)
        small.goto(args.url + "/")
        small.wait_for_selector("text=Same inspections, more fraud found", timeout=20000)
        small.get_by_role("button", name="Skip to the end").click()
        small.wait_for_timeout(1200)
        small.screenshot(path=str(shots / "15_control_room_1366.png"))
        browser.close()

    if args.offline:
        print(f"offline mode: {len(blocked)} external request(s) blocked {blocked[:3]}")
    if errors:
        print("FAIL - console errors:")
        for e in errors:
            print("  ", e)
        return 1
    print(f"OK - every v2 route rendered without console errors; screenshots in {shots}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
