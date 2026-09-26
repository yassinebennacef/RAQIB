"""Assistant RAQIB: a grounded helper chat (FR / AR / EN). It explains; it never scores, ranks, picks a lane or decides.

Grounding without internet or embeddings: BM25 over the sections of docs/assistant_kb.md (generated from the measured
artifacts) + the computed facts of the declaration being viewed. The LLM answers only from those; guards check every
number, accusatory wording and the language; one retry at temperature 0; otherwise a FAQ answer (the best section).
A question that is really a filter request ("montre-moi les rouges de Chine") returns the parsed filter instead.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
from functools import lru_cache

from .. import config as C
from . import client
from .brief import _language_ok
from .guard import banned_claims, unmatched_numbers
from . import config as LLM_CONFIG

KB_PATH = C.ROOT / "docs" / "assistant_kb.md"
CACHE_DIR = C.ARTIFACTS / "assistant_cache"
STARTERS = {
    "declaration": {"fr": ["Pourquoi cette déclaration est ROUGE ?", "Que dois-je vérifier en priorité ?",
                           "Que ferait la règle actuelle ?", "Que veut dire « désaccord des modèles » ?"],
                    "en": ["Why is this declaration RED?", "What should I check first?", "What would the current rule do?",
                           "What does 'models disagree' mean?"],
                    "ar": ["لماذا هذا التصريح في المسار الأحمر؟", "ما الذي يجب أن أتحقق منه أولًا؟",
                           "ماذا كانت ستفعل القاعدة الحالية؟", "ماذا يعني اختلاف النموذجين؟"]},
    "general": {"fr": ["Comment RAQIB choisit les contrôles ?", "Que signifie précision à 5 % ?",
                       "D'où viennent les données ?", "Que fait l'exploration ?"],
                "en": ["How does RAQIB choose the inspections?", "What does precision at 5% mean?",
                       "Where does the data come from?", "What does exploration do?"],
                "ar": ["كيف يختار رقيب عمليات التفتيش؟", "ماذا تعني الدقة عند 5%؟", "من أين تأتي البيانات؟", "ما هو الاستكشاف؟"]},
}


def _cache_key(q: str, lang: str, page: str, facts: dict | None) -> str:
    ctx = facts.get("declaration_id") if facts else ("decl" if page.startswith("/declaration") else "general")
    raw = f"raqib-assistant-v2|{lang}|{ctx}|{' '.join(_tokens(q))}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
LANG_NAME = {"fr": "French", "ar": "Modern Standard Arabic", "en": "English"}
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}, "page": {"type": "string"}},
          "required": ["answer", "page"]}
STOP = set("le la les de des du un une et ou en au aux a à est sont que qui quoi pour par sur dans ce cette ces il elle "
           "on je tu vous nous se sa son ses leur leurs pas ne plus comment pourquoi quel quelle quels quelles the a an of "
           "to is are what why how which in on for with and or it this that do does raqib".split())
FILTER_VERBS = ["montre", "montrez", "affiche", "affichez", "liste", "listez", "filtre", "cherche", "trouve", "show", "list",
                "find", "filter", "display", "اعرض", "أظهر", "ابحث"]
PAGE_NAMES = {"/": "Salle de contrôle", "/worklist": "Worklist", "/declaration": "Inspecteur de la déclaration",
              "/explainability": "Explainability", "/impact": "Impact simulator", "/lab": "Model lab",
              "/model-card": "Model card", "/journal": "Decision journal", "/about": "About", "/score": "Try a declaration"}
REFUSAL = {"fr": "Je ne trouve pas cette information dans la base RAQIB. Je peux expliquer les voies, les modèles, les "
                 "résultats mesurés ou une déclaration ; voir la page About.",
           "en": "I cannot find this in the RAQIB knowledge base. I can explain the lanes, the models, the measured results "
                 "or a declaration; see the About page.",
           "ar": "لا أجد هذه المعلومة في قاعدة معارف رقيب. يمكنني شرح المسارات والنماذج والنتائج المقاسة أو تصريح معيّن؛ راجع صفحة About."}
FAQ_LEAD = {"fr": "", "en": "(Answer from the French knowledge base) ", "ar": "(إجابة من قاعدة المعارف بالفرنسية) "}
SYSTEM = ("You are the RAQIB assistant for customs officers. Answer ONLY from the SECTIONS and FACTS provided. "
          "If the answer is not there, say that you do not find it and point to the right page. Answer in {lang}, in at "
          "most {n} short sentences. Never call goods or people fraudulent: speak of risk indicators. Never recommend a lane "
          "different from RAQIB's, never decide: the officer decides. Do not invent numbers. In 'page', give the page "
          "to open for details (one of: {pages}).")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


AR_STOP = {"ما", "ماذا", "من", "في", "على", "هل", "هو", "هي", "أين", "الى", "إلى", "عن", "هذا", "هذه", "يعني"}


def _norm_ar(t: str) -> str:
    """Strip the Arabic definite article / common prefixes so that البيانات ~ بيانات."""
    for pre in ("وال", "بال", "لل", "ال"):
        if t.startswith(pre) and len(t) - len(pre) >= 3:
            return t[len(pre):]
    return t


def _tokens(s: str) -> list[str]:
    toks = [_norm_ar(t) for t in re.findall(r"[\w%]+", _fold(s))]
    return [t for t in toks if t not in STOP and t not in AR_STOP and len(t) > 1]


@lru_cache(maxsize=1)
def load_kb() -> list[dict]:
    if not KB_PATH.exists():
        return []
    secs, cur = [], None
    for line in KB_PATH.read_text(encoding="utf-8").splitlines():
        m = re.match(r"## (\w+) \| (.+)", line)
        if m:
            cur = {"key": m.group(1), "title": m.group(2).strip(), "keywords": "", "page": "/", "text": ""}
            secs.append(cur)
        elif cur is not None and line.startswith("keywords:"):
            cur["keywords"] = line[9:].strip()
        elif cur is not None and line.startswith("page:"):
            cur["page"] = line[5:].strip()
        elif cur is not None and line.strip():
            cur["text"] += (" " if cur["text"] else "") + line.strip()
    for s in secs:
        s["toks"] = _tokens(f"{s['title']} {s['title']} {s['keywords']} {s['keywords']} {s['text']}")
    return secs


def retrieve(q: str, k: int = 3, page: str | None = None) -> list[tuple[dict, float]]:
    """BM25 over the KB sections (keywords and title count twice); a small bonus for the current page."""
    secs = load_kb()
    if not secs:
        return []
    qt = _tokens(q)
    n = len(secs)
    avg = sum(len(s["toks"]) for s in secs) / n
    df: dict[str, int] = {}
    for s in secs:
        for t in set(s["toks"]):
            df[t] = df.get(t, 0) + 1
    scored = []
    for s in secs:
        tf: dict[str, int] = {}
        for t in s["toks"]:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t in qt:
            f = tf.get(t, 0)
            if not f:
                # prefix match (plural / conjugation): "rouges" ~ "rouge"
                f = sum(v for w, v in tf.items() if len(t) > 5 and len(w) > 5 and w[:6] == t[:6])
                f = 0.5 * f
            if f:
                idf = math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
                score += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(s["toks"]) / avg))
        if page and s["page"] != "/" and page.startswith(s["page"]):
            score += 0.5
        scored.append((s, score))
    scored.sort(key=lambda x: -x[1])
    return scored[:k]


def is_filter_request(q: str) -> bool:
    ql = _fold(q)
    return any(re.search(rf"(?<!\w){re.escape(_fold(v))}", ql) for v in FILTER_VERBS)


def _asks_about_declaration(q: str) -> bool:
    folded = _fold(q)
    return any(w in folded for w in (
        "pourquoi", "why", "rouge", "red", "verifier", "check", "regle", "rule",
        "لماذا", "أحمر", "الأحمر", "المسار", "القاعدة",
    ))


def _asks_why_red(q: str) -> bool:
    folded = _fold(q)
    why = any(w in folded for w in ("pourquoi", "why", "لماذا"))
    red = any(w in folded for w in ("rouge", "red", "احمر", "الأحمر"))
    return why and red


def _faq_guard_passed(text: str, lang: str, evidence: dict, in_scope: bool) -> bool:
    language_ok = _language_ok(text, lang) or text.startswith(FAQ_LEAD[lang])
    return (in_scope and not unmatched_numbers(text, evidence) and not banned_claims(text) and language_ok)


def _faq(q: str, lang: str, hits: list[tuple[dict, float]], facts: dict | None) -> str:
    if facts and _asks_about_declaration(q):
        fraud = facts.get("fraud_risk_percent")
        safety = facts.get("safety_risk_percent")
        decision = facts.get("current_rule_decision")
        if lang == "ar":
            return (f"هذا التصريح في المسار الأحمر للفحص المادي. مؤشرات الخطر المحسوبة: خطر الغش {fraud}٪ "
                    f"وخطر السلامة {safety}٪. كانت القاعدة الحالية ستقوم بـ"
                    f"{'فحص التصريح' if decision == 'inspect' else 'الإفراج عن التصريح'}؛ وهذا لا يغيّر مسار رقيب. "
                    "افتح صفحة فاحص التصريح للاطلاع على الأسباب الأربعة وشلال المخاطر.")
        if lang == "en":
            return (f"This declaration is in RAQIB's RED lane for physical inspection. Its calculated risk indicators "
                    f"are {fraud}% for fraud and {safety}% for safety. The current rule would "
                    f"{'inspect' if decision == 'inspect' else 'release'} it; that does not change RAQIB's lane. "
                    "Open the declaration inspector for the four reasons and risk waterfall.")
        return (f"Cette déclaration est en voie ROUGE (inspection physique) selon RAQIB. Ses indicateurs de risque "
                f"calculés sont de {fraud} % pour la fraude et de {safety} % pour la sécurité. La règle actuelle "
                f"l'aurait {'inspectée' if decision == 'inspect' else 'libérée'} ; cela ne change pas la voie RAQIB. "
                "Ouvrez l'inspecteur de la déclaration pour les quatre raisons et la cascade des risques.")
    if not hits or hits[0][1] < 1.0:
        return REFUSAL[lang]
    s = hits[0][0]
    return f"{FAQ_LEAD[lang]}{s['text']} Page : {PAGE_NAMES.get(s['page'], s['page'])}."


def answer(messages: list[dict], lang: str = "fr", page: str = "/", facts: dict | None = None,
           nlq_parse=None) -> dict:
    lang = lang if lang in LANG_NAME else "fr"
    t0 = time.time()
    q = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "").strip()[:500]
    base = {"lang": lang, "dir": "rtl" if lang == "ar" else "ltr"}
    if not q:
        return {**base, "answer": REFUSAL[lang], "source": "faq", "citations": [], "guard_passed": False, "latency_ms": 0}

    if nlq_parse is not None and is_filter_request(q):
        r = nlq_parse(q)
        if r.get("understood"):
            return {**base, "answer": r["explanation"], "source": r["source"], "kind": "filter", "filter": r["filter"],
                    "question": q, "citations": [{"key": "ask", "title": "Ask RAQIB", "page": "/worklist"}],
                    "guard_passed": True, "latency_ms": int((time.time() - t0) * 1000)}

    single = sum(1 for m in messages if m.get("role") == "user") == 1
    ck = _cache_key(q, lang, page, facts)
    if single and (CACHE_DIR / f"{ck}.json").exists():
        try:
            cached = json.loads((CACHE_DIR / f"{ck}.json").read_text(encoding="utf-8"))
            return {**cached, "cached": True, "latency_ms": int((time.time() - t0) * 1000)}
        except ValueError:
            pass
    hits = retrieve(q, 3, page)
    cites = [{"key": s["key"], "title": s["title"], "page": s["page"]} for s, sc in hits if sc > 0]
    grounded = [s for s, sc in hits if sc >= 1.0]
    in_scope = bool(grounded)
    problems: list[str] = []
    evidence = {"facts": facts or {}, "sections": [s["text"] for s in grounded]}
    if facts and in_scope and _asks_why_red(q):
        faq = _faq(q, lang, hits, facts)
        return {**base, "answer": faq, "source": "faq", "citations": cites, "guard_passed":
                _faq_guard_passed(faq, lang, evidence, in_scope), "out_of_scope": False,
                "attempts": 0, "latency_ms": int((time.time() - t0) * 1000)}
    attempts = 0
    if client.available() and in_scope:
        lean = dict(facts or {})
        if lean.get("risk_indicators"):
            lean["risk_indicators"] = lean["risk_indicators"][:3]
        ctx = {"SECTIONS": [{"title": s["title"], "text": s["text"], "page": PAGE_NAMES.get(s["page"], s["page"])}
                            for s in grounded[:2 if facts else 3]],
               "FACTS": lean}
        history = [f"{m['role']}: {str(m.get('content', ''))[:400]}" for m in messages[-6:-1]]
        user = (("Conversation so far:\n" + "\n".join(history) + "\n\n") if history else "") + \
               f"Question: {q}\n\nCONTEXT = {json.dumps(ctx, ensure_ascii=False)}"
        system = SYSTEM.format(lang=LANG_NAME[lang], pages=", ".join(PAGE_NAMES.values()), n=3 if lang == "ar" else 4)
        for temperature in (0.2, 0.0):
            remaining = LLM_CONFIG.TIMEOUT - (time.time() - t0)
            if remaining <= 0:
                problems.append("assistant timeout")
                break
            try:
                attempts += 1
                content, ms = client.chat(system, user, schema=SCHEMA, temperature=temperature,
                                          num_predict=380 if lang == "ar" else 230, timeout=remaining)
                obj = json.loads(content)
                text = re.sub(r"\s+", " ", str(obj.get("answer", ""))).strip()
                pg = str(obj.get("page", "")).strip()
                if pg and pg not in text:
                    text = f"{text}\n→ {pg}"
            except (client.LLMError, ValueError) as exc:
                problems.append(str(exc))
                continue
            problems = []
            bad = unmatched_numbers(text, evidence)
            if bad:
                problems.append(f"numbers not in the sources: {', '.join(bad[:5])}")
            if banned_claims(text):
                problems.append("banned claims")
            if not _language_ok(text, lang) and len(text) > 80:
                problems.append(f"not in {LANG_NAME[lang]}")
            if facts and _asks_about_declaration(q) and any(
                marker in _fold(text) for marker in ("not enough context", "insufficient context", "لا توجد معلومات كافية")
            ):
                problems.append("answer declined despite declaration facts")
            if len(text) < 20:
                problems.append("too short")
            if not problems:
                out = {**base, "answer": text, "source": "qwen3-4b", "citations": cites, "guard_passed": True,
                       "attempts": attempts, "latency_ms": int((time.time() - t0) * 1000)}
                if single:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    (CACHE_DIR / f"{ck}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                return {**out, "cached": False}
    faq = _faq(q, lang, hits, facts)
    return {**base, "answer": faq, "source": "faq", "citations": cites if in_scope else [],
            "guard_passed": _faq_guard_passed(faq, lang, evidence, in_scope), "out_of_scope": not in_scope,
            "rejected": problems, "attempts": attempts,
            "latency_ms": int((time.time() - t0) * 1000)}


def pregenerate(build_facts, decl_ids: list[str]) -> None:
    """Background: cache the starter questions (demo declarations + general pages) in FR / AR / EN."""
    import threading

    def run() -> None:
        jobs = [(lang, q, f"/declaration/{d}", d) for d in decl_ids for lang, qs in STARTERS["declaration"].items() for q in qs]
        jobs += [(lang, q, "/", None) for lang, qs in STARTERS["general"].items() for q in qs]
        for lang, q, page, d in jobs:
            try:
                answer([{"role": "user", "content": q}], lang, page, build_facts(d) if d else None)
            except Exception:  # noqa: BLE001 - best effort
                continue
    threading.Thread(target=run, daemon=True).start()
