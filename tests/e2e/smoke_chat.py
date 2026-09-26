"""Browser test of the 'Demander à Qwen' panel (needs the server AND a local Ollama with Qwen3).

Usage: .venv/Scripts/python tests/e2e/smoke_chat.py [--url http://127.0.0.1:8000] [--shots DIR]
Checks: launcher on every page, a streamed answer, the conversation kept across in-app navigation and a reload,
declaration context on /declaration/<id>, no console errors.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROUTES = ["/", "/worklist", "/score", "/tunisie", "/impact", "/explainability", "/lab", "/model-card", "/journal",
          "/about", "/assistant"]


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
    ap.add_argument("--shots", default="")
    args = ap.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    red_id = json.loads(opener.open(args.url + "/api/worklist?lane=RED&page_size=1").read())["items"][0]["id"]
    errors: list[str] = []
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1500, "height": 950})
        page.on("console", lambda m: errors.append(f"[{page.url}] console: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[{page.url}] pageerror: {e}"))

        def wait_answer(timeout_s: int = 150) -> str:
            page.get_by_test_id("chat-send").wait_for(state="visible", timeout=timeout_s * 1000)
            bubbles = page.get_by_test_id("chat-panel").locator("div.rounded-2xl")
            return bubbles.nth(bubbles.count() - 1).inner_text()

        for r in ROUTES + [f"/declaration/{red_id}"]:
            page.goto(args.url + r)
            page.wait_for_load_state("networkidle")
            if page.get_by_test_id("chat-open").count() + page.get_by_test_id("chat-panel").count() == 0:
                errors.append(f"[{r}] no chat launcher")

        page.goto(args.url + "/")
        page.wait_for_load_state("networkidle")
        page.evaluate("sessionStorage.removeItem('raqib_chat')")
        page.reload()
        page.get_by_test_id("chat-open").click()
        page.get_by_test_id("chat-input").fill("Quelle est la capitale de la Tunisie ? Réponds en une phrase.")
        page.keyboard.press("Enter")
        a1 = wait_answer()
        print("A1:", a1[:160].replace("\n", " "))
        if "Tunis" not in a1:
            errors.append(f"general answer without 'Tunis': {a1[:120]}")

        page.get_by_role("link", name="Contexte tunisien").first.click()  # in-app navigation
        page.wait_for_load_state("networkidle")
        if "Tunis" not in page.get_by_test_id("chat-panel").inner_text():
            errors.append("conversation lost after in-app navigation")
        page.reload()
        page.wait_for_load_state("networkidle")
        if page.get_by_test_id("chat-panel").count() == 0 or "Tunis" not in page.get_by_test_id("chat-panel").inner_text():
            errors.append("conversation lost after reload")

        page.goto(args.url + f"/declaration/{red_id}")
        page.wait_for_load_state("networkidle")
        page.get_by_test_id("chat-input").fill("Dans quel couloir est cette déclaration et pourquoi ? Réponds en 3 phrases.")
        page.keyboard.press("Enter")
        a2 = wait_answer()
        print("A2:", a2[:300].replace("\n", " "))
        if not any(w in a2.lower() for w in ("rouge", "red", "inspection")):
            errors.append(f"declaration answer does not mention the lane: {a2[:160]}")
        if args.shots:
            Path(args.shots).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(args.shots) / "chat_panel.png"))
        page.get_by_test_id("chat-close").click()
        if page.get_by_test_id("chat-open").count() != 1:
            errors.append("panel does not minimise")
        browser.close()
    if errors:
        print("FAIL")
        for e in errors:
            print(" ", e)
        return 1
    print("OK - chat panel on every page, streamed answers, context kept across navigation and reload")
    return 0


if __name__ == "__main__":
    sys.exit(main())
