"""Officer brief (FR / AR / EN) written by the local LLM from verified facts only.

Flow: facts (from the models' outputs) -> Qwen3 with a JSON schema -> guards (numbers, banned claims,
language, no echo) -> retry once at temperature 0 -> otherwise the deterministic template.
LLM results are cached in artifacts/brief_cache/{id}_{lang}.json.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone

from .. import config as C
from . import client
from .guard import banned_claims, unmatched_numbers

CACHE_DIR = C.ARTIFACTS / "brief_cache"
LANG_NAME = {"fr": "French", "ar": "Modern Standard Arabic", "en": "English"}
SUGGESTED = {"fr": "Contrôle suggéré", "ar": "الفحص المقترح", "en": "Suggested check"}
SCHEMA = {"type": "object", "properties": {"brief": {"type": "string"}, "suggested_check": {"type": "string"}},
          "required": ["brief", "suggested_check"]}
SYSTEM = ("You are an assistant writing a short inspection brief for a customs officer. Use ONLY the facts provided "
          "in JSON. Do not invent numbers, names, or causes. Do not say the goods ARE fraudulent: say 'risk indicators'. "
          "Write {length} in {lang}. In suggested_check, name in a few words what to "
          "verify (documents, value, origin, physical exam) based on the reasons, in {lang}. {terms}")
LENGTH = {"fr": "exactly 4 short sentences (at most 80 words)", "en": "exactly 4 short sentences (at most 80 words)",
          "ar": "exactly 3 short sentences (at most 55 words)"}
TERMS = {
    "fr": ("Vocabulaire : déclaration, indicateurs de risque, voie rouge (inspection physique), voie jaune (contrôle "
           "documentaire), voie verte (mainlevée), agent des douanes, règle actuelle."),
    "ar": ("استعمل المصطلحات: التصريح الديواني، مؤشرات الخطر، المسار الأحمر (تفتيش مادي)، المسار الأصفر (مراقبة وثائقية)، "
           "المسار الأخضر (رفع اليد)، العون الديواني، القاعدة الحالية. لا تقل إن البضاعة مغشوشة."),
    "en": "",
}
LANE_WORDS = {"RED": "RED (physical inspection)", "YELLOW": "YELLOW (document check)", "GREEN": "GREEN (release)"}
ECHO_MARKERS = ["FACTS =", "TASK:", "4-6 sentences", "4 short sentences", "3 short sentences", "suggested_check", "Modern Standard Arabic",
                "Use ONLY the facts"]


def facts_from_detail(d: dict) -> dict:
    """Compact facts for the LLM, built ONLY from the models' computed outputs for one declaration."""
    dc, ai, rule, hist = d["declaration"], d["ai"], d["rule"], d["history"]
    imp = hist["importer"]
    facts = {
        "declaration_id": dc["id"], "date": dc["date"], "office": dc["office_label"], "origin": dc["origin"],
        "product": f"HS {dc['hs6']} {dc['hs_desc'][:90]}",
        "lane": LANE_WORDS[ai["lane"]],
        "fraud_risk_percent": round(ai["p_fraud"] * 100, 1),
        "safety_risk_percent": round(ai["p_critical"] * 100, 1),
        "safety_alert": bool(ai["alert"]),
        "models_disagree": bool(ai.get("uncertain", False)),
        "risk_indicators": [f"{'raises' if r['direction'] == 'raises' else 'lowers'} risk: {r['text']}"
                            for r in ai["reasons_fraud"][:4]],
        "current_rule_decision": "inspect" if rule["decision"] == "INSPECT" else "release",
    }
    if ai["alert"] and ai.get("reasons_critical"):
        facts["safety_alert_reason"] = ai["reasons_critical"][0]["text"]
    if imp.get("past_declarations"):
        facts["importer_past_fraud_rate_percent"] = round((imp.get("fraud_rate") or 0) * 100, 1)
        facts["importer_past_declarations"] = imp["past_declarations"]
    return facts


def _language_ok(text: str, lang: str) -> bool:
    if lang == "ar":
        letters = [ch for ch in text if ch.isalpha()]
        return bool(letters) and sum("؀" <= ch <= "ۿ" for ch in letters) / len(letters) > 0.6
    words = {"fr": [" le ", " la ", " de ", " des ", " est ", " et ", " du "],
             "en": [" the ", " of ", " and ", " is ", " to ", " a ", " with ", " for ", " risk ", " should "]}[lang]
    low = f" {text.lower()} "
    return sum(w in low for w in words) >= (3 if lang == "fr" else 2)


def check(text: str, facts: dict, lang: str) -> list[str]:
    """Reasons to reject a generated brief (empty list = accepted)."""
    problems = []
    bad = unmatched_numbers(text, facts)
    if bad:
        problems.append(f"numbers not in facts: {', '.join(bad[:5])}")
    claims = banned_claims(text)
    if claims:
        problems.append(f"banned claims: {', '.join(claims)}")
    if any(m in text for m in ECHO_MARKERS):
        problems.append("echoes the instructions")
    if len(text) < 120:
        problems.append("too short")
    if not _language_ok(text, lang):
        problems.append(f"not in {LANG_NAME[lang]}")
    return problems


def _generate(facts: dict, lang: str, temperature: float, background: bool = False) -> tuple[str, int]:
    name = LANG_NAME[lang]
    user = (f"Write the inspection brief in {name} for the declaration below.\n"
            f"FACTS = {json.dumps(facts, ensure_ascii=False)}")
    content, ms = client.chat(SYSTEM.format(lang=name, terms=TERMS[lang], length=LENGTH[lang]), user, schema=SCHEMA, temperature=temperature,
                              num_predict=320, background=background)
    obj = json.loads(content)
    brief = re.sub(r"\s+", " ", str(obj.get("brief", ""))).strip()
    check_line = re.sub(r"\s+", " ", str(obj.get("suggested_check", ""))).strip()
    return f"{brief}\n{SUGGESTED[lang]}: {check_line}", ms


def _cache_path(decl_id: str, lang: str):
    return CACHE_DIR / f"{decl_id}_{lang}.json"


def cached(decl_id: str, lang: str) -> dict | None:
    p = _cache_path(decl_id, lang)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


def brief(decl_id: str, lang: str, facts: dict, template_text: str, refresh: bool = False,
          background: bool = False) -> dict:
    lang = lang if lang in LANG_NAME else "fr"
    base = {"lang": lang, "dir": "rtl" if lang == "ar" else "ltr", "facts_used": facts}
    if not refresh:
        c = cached(decl_id, lang)
        if c:
            return {**c, "facts_used": facts, "cached": True}
    problems: list[str] = []
    llm_down = not client.available()
    if not llm_down:
        for temperature in (0.2, 0.0):
            try:
                text, ms = _generate(facts, lang, temperature, background)
            except client.LLMError as exc:
                problems.append(str(exc))
                llm_down = True
                break
            except (ValueError, KeyError) as exc:
                problems.append(f"invalid JSON answer ({exc})")
                continue
            problems = check(text, facts, lang)
            if not problems:
                out = {**base, "text": text, "source": "qwen3-4b", "model": client.status()["model"],
                       "guard_passed": True, "latency_ms": ms, "cached": False,
                       "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _cache_path(decl_id, lang).write_text(json.dumps({k: v for k, v in out.items() if k != "facts_used"},
                                                                 ensure_ascii=False, indent=2), encoding="utf-8")
                return out
    # llm_error tells the UI why it got the template although the local LLM is switched on (never silent).
    # "unavailable": Ollama down, model missing or timeout; "rejected": Qwen answered but the guard refused the text.
    llm_error = llm_fallback = None
    if client.enabled():
        llm_fallback = "unavailable" if llm_down else "rejected"
        llm_error = (client.status()["last_error"] if llm_down else None) or "; ".join(problems) or "local LLM not available"
    return {**base, "text": template_text, "source": "template", "model": None, "guard_passed": False,
            "latency_ms": 0, "cached": False, "rejected": problems, "llm_fallback": llm_fallback,
            "llm_error": llm_error}


def pregenerate(jobs: list[tuple[str, str]], build) -> None:
    """Background: generate and cache briefs. `build(decl_id) -> (facts, template_text)`."""
    def run() -> None:
        client.warm_up()
        for decl_id, lang in jobs:
            if cached(decl_id, lang):
                continue
            try:
                facts, template_text = build(decl_id)
                brief(decl_id, lang, facts, template_text, background=True)
            except Exception:  # noqa: BLE001 - background best effort
                continue
    threading.Thread(target=run, daemon=True).start()
