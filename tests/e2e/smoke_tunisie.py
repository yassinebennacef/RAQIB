"""Browser smoke test of the Tunisian edition: every v2 route in TND, EUR and USD - no console error, no NaN.

Usage (server running with the v2 UI):  .venv/Scripts/python tests/e2e/smoke_tunisie.py [--url http://127.0.0.1:8000]
Every request that does not go to --url is blocked (offline demo).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

from playwright.sync_api import sync_playwright

ROUTES = ["/", "/worklist", "/score", "/tunisie", "/impact", "/explainability", "/lab", "/model-card", "/journal",
          "/about", "/assistant"]
LABEL = {"tnd": "TND", "eur": "EUR", "usd": "USD"}
# pages that must show at least one amount in the chosen currency
MONEY_PAGES = {"/tunisie", "/impact", "/about", "declaration"}  # worklist value column is hidden by default


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
    with urllib.request.urlopen(args.url + "/api/worklist?lane=RED&page_size=1") as r:
        red_id = json.loads(r.read())["items"][0]["id"]
    routes = ROUTES + [f"/declaration/{red_id}"]
    errors: list[str] = []
    blocked: list[str] = []
    checks: list[str] = []
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})

        def gate(route):
            if route.request.url.startswith(args.url):
                route.continue_()
            else:
                blocked.append(route.request.url)
                route.abort()

        page.route("**/*", gate)
        page.on("console", lambda m: errors.append(f"[{page.url}] console {m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[{page.url}] pageerror: {e}"))

        for cur in ("tnd", "eur", "usd"):
            page.goto(args.url + "/")
            page.wait_for_load_state("networkidle")
            page.get_by_test_id(f"cur-{cur}").first.click()
            for r in routes:
                page.goto(args.url + r)  # the choice must survive navigation (session memory)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(700)
                text = page.inner_text("body")
                if r == "/score" and f"Valeur {LABEL[cur]}" not in text:
                    errors.append(f"[{cur} /score] value input not in {LABEL[cur]}")
                if re.search(r"\bNaN\b", text):
                    errors.append(f"[{cur} {r}] NaN on the page")
                if "Infinity" in text:
                    errors.append(f"[{cur} {r}] Infinity on the page")
                if page.get_by_test_id(f"cur-{cur}").first.get_attribute("aria-checked") != "true":
                    errors.append(f"[{cur} {r}] currency switch lost the choice")
                key = "declaration" if r.startswith("/declaration") else r
                amount = rf"\d(?:[\s  ]?(?:k|M|Md|G|B))?[\s  ]{LABEL[cur]}\b"
                if key in MONEY_PAGES and not re.search(amount, text):
                    errors.append(f"[{cur} {r}] no amount in {LABEL[cur]}")
                others = [LABEL[c] for c in LABEL if c != cur]
                if key == "/worklist" and any(re.search(rf"\d {o}\b", text) for o in others):
                    errors.append(f"[{cur} {r}] amounts in another currency")
                # the only KRW allowed is the rate definition on /about ("1 USD = 1 158,87 KRW")
                shown_krw = [m for m in re.findall(r"[\d.,]+[kMB]? ?KRW", text) if r != "/about"]
                if shown_krw:
                    errors.append(f"[{cur} {r}] raw KRW amounts shown: {shown_krw[:3]}")
                if r == "/tunisie":
                    for must in ("UN Comtrade (Tunisie, 2024)", "Écart miroir", "sous-facturation, pas une preuve",
                                 "données de déclaration synthétiques coréennes × prix de référence réels tunisiens"):
                        if must not in text:
                            errors.append(f"[{cur} /tunisie] missing: {must}")
                if key == "declaration" and "Référence tunisienne" not in text:
                    errors.append(f"[{cur} {r}] missing the Tunisian reference card")
                if r == "/impact" and "Droits et taxes en jeu" not in text:
                    errors.append(f"[{cur} /impact] missing the duties card")
                if r == "/about" and "taux de référence du 23/09/2026" not in text:
                    errors.append(f"[{cur} /about] missing the exchange-rate note")
                checks.append(f"{cur} {r}")
        browser.close()
    print(f"{len(checks)} page checks, {len(blocked)} external requests blocked")
    if blocked:
        print("blocked:", sorted(set(blocked))[:10])
    if errors:
        print("FAIL")
        for e in errors[:60]:
            print(" ", e)
        return 1
    print("OK - every route in TND, EUR and USD: no console error, no NaN, amounts in the chosen currency")
    return 0


if __name__ == "__main__":
    sys.exit(main())
