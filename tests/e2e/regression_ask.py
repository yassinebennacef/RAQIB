"""Regression test for "Ask RAQIB" (the 'Comprendre' button used to look silent).

Usage (server running):  .venv/Scripts/python tests/e2e/regression_ask.py [--url http://127.0.0.1:8000]
Checks: click and Enter both return chips; the FR example answers in < 2 s; the Ctrl+K path works; a very long
question never fails silently; a busy/slow LLM shows a visible 'Analyse en cours…' status; no console error.
"""
from __future__ import annotations

import argparse
import sys
import time

from playwright.sync_api import sync_playwright

FR = "déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%"


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
    args = ap.parse_args()
    errors, results = [], []

    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on("console", lambda m: errors.append(f"console {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror {e}"))

        def ask(text: str, how: str) -> float:
            page.goto(args.url + "/worklist")
            box = page.get_by_label("Ask RAQIB in French, English or Arabic")
            box.wait_for(timeout=20000)
            box.fill(text)
            t0 = time.time()
            if how == "enter":
                box.press("Enter")
            else:
                page.get_by_role("button", name="Comprendre").click()
            page.wait_for_selector("[data-testid=ask-result], [data-sonner-toast]", timeout=30000)
            return time.time() - t0

        dt = ask(FR, "click")
        ok = page.locator("[data-testid=ask-result]").count() == 1 and page.locator("text=Origin CN").count() > 0
        results.append(("click -> chips (FR example)", ok and dt < 2, f"{dt:.2f}s"))
        page.get_by_role("button", name="Appliquer").click()
        page.wait_for_selector("text=Filtre Ask RAQIB appliqué", timeout=10000)
        results.append(("Appliquer -> filter applied", True, ""))

        dt = ask(FR, "enter")
        results.append(("Enter -> chips", page.locator("[data-testid=ask-result]").count() == 1, f"{dt:.2f}s"))

        dt = ask("montre les déclarations " * 40, "click")
        visible = page.locator("[data-testid=ask-result]").count() + page.locator("[data-sonner-toast]").count()
        results.append(("very long question -> visible answer or toast", visible > 0, f"{dt:.2f}s"))

        page.goto(args.url + "/worklist")
        page.get_by_label("Ask RAQIB in French, English or Arabic").fill("marchandises venues de loin par un chemin étrange")
        page.get_by_role("button", name="Comprendre").click()
        status_seen = False
        for _ in range(20):
            if page.locator("text=Analyse en cours").count() or page.locator("[data-testid=ask-result]").count() \
                    or page.locator("[data-sonner-toast]").count():
                status_seen = True
                break
            time.sleep(0.05)
        results.append(("free phrasing -> visible status / result immediately", status_seen, ""))
        page.wait_for_selector("[data-testid=ask-result], [data-sonner-toast]", timeout=30000)

        page.goto(args.url + "/")
        page.wait_for_selector("text=Same inspections", timeout=20000)
        page.keyboard.press("Control+k")
        page.keyboard.type("rouges de Chine au chapitre 85")
        page.wait_for_selector("text=Ask RAQIB:", timeout=10000)
        page.keyboard.press("Enter")
        page.wait_for_selector("[data-testid=ask-result]", timeout=30000)
        results.append(("Ctrl+K -> worklist with chips", True, ""))
        browser.close()

    ok_all = all(r[1] for r in results) and not errors
    for name, ok, extra in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name} {extra}")
    for e in errors:
        print("console error:", e)
    print("REGRESSION", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
