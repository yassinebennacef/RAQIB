""""Ask RAQIB": a natural-language question (FR / EN / AR) -> a strict, validated worklist filter.

The LLM (JSON-schema output, temperature 0) only proposes a filter; it is validated against the dataset's
real vocabularies, invalid values are dropped with warnings, and the officer sees it as chips and must click
Apply. A rule-based parser is always available as fallback. Nothing but this filter is ever executed.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from . import client


class NLQFilter(BaseModel):
    lane: list[Literal["RED", "YELLOW", "GREEN"]] | None = None
    min_fraud: float | None = Field(default=None, ge=0, le=1)
    safety_only: bool = False
    uncertain_only: bool = False
    origin: list[str] | None = None
    hs_prefix: list[str] | None = None
    office: list[str] | None = None
    importer: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    sort: Literal["fraud_desc", "critical_desc", "date_desc"] = "fraud_desc"
    limit: int = Field(default=50, ge=1, le=500)


SCHEMA = {
    "type": "object",
    "properties": {
        "lane": {"type": ["array", "null"], "items": {"type": "string", "enum": ["RED", "YELLOW", "GREEN"]}},
        "min_fraud": {"type": ["number", "null"]},
        "safety_only": {"type": "boolean"},
        "uncertain_only": {"type": "boolean"},
        "origin": {"type": ["array", "null"], "items": {"type": "string"}},
        "hs_prefix": {"type": ["array", "null"], "items": {"type": "string"}},
        "office": {"type": ["array", "null"], "items": {"type": "string"}},
        "importer": {"type": ["string", "null"]},
        "date_from": {"type": ["string", "null"]},
        "date_to": {"type": ["string", "null"]},
        "sort": {"type": "string", "enum": ["fraud_desc", "critical_desc", "date_desc"]},
        "limit": {"type": "integer"},
    },
    "required": ["lane", "min_fraud", "safety_only", "uncertain_only", "origin", "hs_prefix", "office", "importer",
                 "date_from", "date_to", "sort", "limit"],
}

HS_GLOSSARY = [
    ("85", ["électrique", "electrique", "electrical", "électronique", "electronic", "machines électriques", "كهربائية", "الكهربائية", "إلكترونية", "الإلكترونية"]),
    ("61", ["vêtements", "vetements", "clothing", "garments", "apparel", "habillement", "ملابس", "الملابس"]),
    ("62", ["vêtements", "vetements", "clothing", "garments", "apparel", "habillement", "ملابس", "الملابس"]),
    ("87", ["véhicules", "vehicules", "vehicles", "voitures", "cars", "سيارات", "السيارات", "مركبات", "المركبات"]),
    ("30", ["médicaments", "medicaments", "pharmaceutical", "pharmaceutiques", "medicines", "drugs", "أدوية", "الأدوية"]),
    ("93", ["armes", "arms", "weapons", "أسلحة", "الأسلحة"]),
    ("95", ["jouets", "toys", "ألعاب", "الألعاب"]),
    ("09", ["café", "cafe", "coffee", "thé", "tea", "قهوة"]),
    ("64", ["chaussures", "footwear", "shoes", "أحذية"]),
    ("33", ["cosmétiques", "cosmetiques", "cosmetics", "parfums", "perfume", "مستحضرات التجميل"]),
    ("03", ["poisson", "fish", "سمك", "أسماك"]),
]
COUNTRIES = {
    "CN": ["chine", "china", "chinese", "chinois", "chinoise", "chinoises", "الصين"], "JP": ["japon", "japan", "اليابان"],
    "US": ["états-unis", "etats-unis", "usa", "united states", "america", "amérique", "أمريكا", "الولايات المتحدة"],
    "KR": ["corée", "coree", "korea", "كوريا"], "VN": ["vietnam", "viêt nam", "فيتنام"], "DE": ["allemagne", "germany", "ألمانيا"],
    "IT": ["italie", "italy", "إيطاليا"], "TW": ["taïwan", "taiwan", "تايوان"], "FR": ["france", "فرنسا"],
    "TH": ["thaïlande", "thailande", "thailand", "تايلاند"], "GB": ["royaume-uni", "united kingdom", "uk", "britain", "بريطانيا"],
    "MY": ["malaisie", "malaysia", "ماليزيا"], "IN": ["inde", "india", "الهند"], "TR": ["turquie", "turkey", "تركيا"],
    "ES": ["espagne", "spain", "إسبانيا"], "ID": ["indonésie", "indonesie", "indonesia", "إندونيسيا"],
    "TN": ["tunisie", "tunisia", "تونس"], "NO": ["norvège", "norway", "النرويج"], "AU": ["australie", "australia", "أستراليا"],
}
LANE_WORDS = {"RED": ["rouge", "rouges", "red", "أحمر", "الحمراء", "حمراء"],
              "YELLOW": ["jaune", "jaunes", "yellow", "أصفر", "الصفراء", "صفراء"],
              "GREEN": ["vert", "verts", "verte", "vertes", "green", "أخضر", "الخضراء", "خضراء"]}
SAFETY_WORDS = ["sécurité", "securite", "safety", "menace", "threat", "alerte", "alert", "danger", "أمني", "الأمني",
                "السلامة", "تنبيه", "التنبيه", "خطر أمني"]
UNCERTAIN_WORDS = ["incertain", "incertains", "uncertain", "désaccord", "desaccord", "disagree", "disagreement",
                   "divergent", "غير مؤكد", "غير المؤكدة", "اختلاف", "يختلف"]
MONTHS = {"04": ["avril", "april", "أبريل", "نيسان", "افريل"], "05": ["mai", "may", "مايو", "ماي", "أيار"],
          "06": ["juin", "june", "يونيو", "جوان", "حزيران"]}
MONTH_END = {"04": "30", "05": "31", "06": "30"}


class Vocab:
    """Real values present in the data, used to validate any proposed filter."""

    def __init__(self, origins: set[str], offices: dict[str, str], hs6: set[str], importers: set[str],
                 date_min: str, date_max: str):
        self.origins, self.offices, self.hs6, self.importers = origins, offices, hs6, importers
        self.date_min, self.date_max = date_min, date_max

    def hs_ok(self, prefix: str) -> bool:
        return prefix.isdigit() and 2 <= len(prefix) <= 6 and any(h.startswith(prefix) for h in self.hs6)


def _find_words(q: str, words: list[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", q) for w in words)


def rules_parse(q: str, vocab: Vocab) -> dict:
    """Deterministic parser (always available)."""
    ql = q.lower()
    f: dict = {}
    lanes = [lane for lane, ws in LANE_WORDS.items() if _find_words(ql, ws)]
    if lanes:
        f["lane"] = lanes
    if _find_words(ql, SAFETY_WORDS):
        f["safety_only"] = True
        f["sort"] = "critical_desc"
    if _find_words(ql, UNCERTAIN_WORDS):
        f["uncertain_only"] = True
    m = re.search(r"(?:>=?|≥|au[- ]dessus de|above|over|more than|plus de|supérieur[e]? à|superieur[e]? a|أكثر من|فوق|أعلى من)\s*(\d+(?:[.,]\d+)?)\s*%?", ql)
    if m:
        v = float(m.group(1).replace(",", "."))
        f["min_fraud"] = v / 100 if v > 1 else v
    origins = [iso for iso, names in COUNTRIES.items() if _find_words(ql, names)]
    origins += [t for t in re.findall(r"\b([A-Z]{2})\b", q) if t in vocab.origins and t not in {"HS", "SH", "OK"}]
    if origins:
        f["origin"] = sorted(set(origins))
    hs = re.findall(r"(?:chapitre|chapter|chap\.?|hs|sh|code|الفصل|فصل)\s*(\d{2,6})", ql)
    for code, words in HS_GLOSSARY:
        if _find_words(ql, words):
            hs.append(code)
    if hs:
        f["hs_prefix"] = sorted(set(hs))
    offices = re.findall(r"(?:bureau|office|مكتب|المكتب)\s*(\d{2,3})", ql)
    if offices:
        f["office"] = sorted(set(offices))
    m = re.search(r"(?:importateur|importer|المستورد|مستورد)\s+([A-Za-z0-9]{5,8})", q)
    if m:
        f["importer"] = m.group(1).upper()
    months = [mm for mm, ws in MONTHS.items() if _find_words(ql, ws)]
    if months:
        f["date_from"] = f"2021-{min(months)}-01"
        f["date_to"] = f"2021-{max(months)}-{MONTH_END[max(months)]}"
    m = re.search(r"top\s*(\d{1,3})|(\d{1,3})\s*(?:premières|premiers|premieres|first|أول)|(?:les|the)\s+(\d{1,3})\s+(?:plus|most)", ql)
    if m:
        f["limit"] = int(next(g for g in m.groups() if g))
    if _find_words(ql, ["récent", "récentes", "recent", "latest", "dernières", "الأحدث"]):
        f["sort"] = "date_desc"
    return f


def _system_prompt(vocab: Vocab) -> str:
    offices = "; ".join(f"{k} = {v}" for k, v in list(vocab.offices.items())[:12])
    gloss = "; ".join(f"{code} = {', '.join(ws[:3])}" for code, ws in HS_GLOSSARY)
    return (
        "You convert a customs officer's question (French, English or Arabic) into a JSON filter for the worklist. "
        "Fill only what the question asks; use null / false otherwise. Fields: lane (RED = inspect, YELLOW = document "
        "check, GREEN = release), min_fraud (fraud probability threshold between 0 and 1, e.g. 'above 80%' -> 0.8), "
        "safety_only (public-safety alerts), uncertain_only (the two models disagree), origin (ISO-2 country codes), "
        "hs_prefix (2 to 6 digit HS code prefixes), office (office codes), importer (importer ID), date_from/date_to "
        f"(ISO dates between {vocab.date_min} and {vocab.date_max}; null unless a month or date is asked), "
        "sort (fraud_desc by default; critical_desc only for safety questions; date_desc only for 'recent' / 'latest'), "
        "limit (default 50). "
        f"Office codes: {offices}. HS chapters: {gloss}. "
        "Examples: 'déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%' -> lane [RED], origin [CN], "
        "hs_prefix ['85'], min_fraud 0.8. 'show uncertain cases from office 20' -> uncertain_only true, office ['20']. "
        "'الحالات ذات التنبيه الأمني' -> safety_only true, sort critical_desc."
    )


def validate(raw: dict, vocab: Vocab) -> tuple[NLQFilter, list[str]]:
    """Keep only valid values (checked against the real data); report what was dropped."""
    w: list[str] = []
    out: dict = {}
    lanes = [str(x).upper() for x in (raw.get("lane") or [])]
    good = sorted({x for x in lanes if x in {"RED", "YELLOW", "GREEN"}}, key=["RED", "YELLOW", "GREEN"].index)
    if len(good) < len(set(lanes)):
        w.append(f"ignored lane values: {sorted(set(lanes) - set(good))}")
    out["lane"] = good or None
    mf = raw.get("min_fraud")
    if mf is not None:
        try:
            v = float(mf)
            v = v / 100 if v > 1 else v
            if 0 <= v <= 1:
                out["min_fraud"] = round(v, 4)
            else:
                w.append(f"ignored min_fraud {mf}")
        except (TypeError, ValueError):
            w.append(f"ignored min_fraud {mf}")
    out["safety_only"] = bool(raw.get("safety_only"))
    out["uncertain_only"] = bool(raw.get("uncertain_only"))
    names = {n: iso for iso, ns in COUNTRIES.items() for n in ns}
    origins = []
    for o in raw.get("origin") or []:
        s = str(o).strip()
        iso = s.upper() if s.upper() in vocab.origins else names.get(s.lower())
        if iso and iso in vocab.origins:
            origins.append(iso)
        else:
            w.append(f"ignored origin '{s}' (not in the data)")
    out["origin"] = sorted(set(origins)) or None
    hs = []
    for h in raw.get("hs_prefix") or []:
        s = re.sub(r"\D", "", str(h))
        if vocab.hs_ok(s):
            hs.append(s)
        else:
            w.append(f"ignored HS prefix '{h}'")
    out["hs_prefix"] = sorted(set(hs)) or None
    offices = []
    for o in raw.get("office") or []:
        s = re.sub(r"\D", "", str(o))
        if s in vocab.offices:
            offices.append(s)
        else:
            w.append(f"ignored office '{o}'")
    out["office"] = sorted(set(offices), key=int) or None
    imp = raw.get("importer")
    if imp:
        s = str(imp).strip().upper()
        if s in vocab.importers:
            out["importer"] = s
        else:
            w.append(f"ignored importer '{imp}' (unknown)")
    for k in ("date_from", "date_to"):
        v = raw.get(k)
        if v:
            s = str(v)[:10]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) and vocab.date_min <= s <= vocab.date_max:
                out[k] = s
            else:
                w.append(f"ignored {k} '{v}' (outside {vocab.date_min}..{vocab.date_max})")
    if out.get("date_from") == vocab.date_min and out.get("date_to") == vocab.date_max:
        out.pop("date_from")
        out.pop("date_to")  # the whole period: not a filter
    if raw.get("sort") in ("fraud_desc", "critical_desc", "date_desc"):
        out["sort"] = raw["sort"]
    try:
        out["limit"] = max(1, min(500, int(raw.get("limit") or 50)))
    except (TypeError, ValueError):
        out["limit"] = 50
    return NLQFilter(**out), w


def explain(f: NLQFilter, offices: dict[str, str] | None = None) -> str:
    """One-line human summary built from the FILTER (deterministic)."""
    parts = []
    if f.lane:
        parts.append("lane " + "/".join(f.lane))
    if f.safety_only:
        parts.append("public-safety alerts only")
    if f.uncertain_only:
        parts.append("models disagree")
    if f.min_fraud is not None:
        parts.append(f"fraud risk ≥ {f.min_fraud * 100:.0f}%")
    if f.origin:
        parts.append("origin " + ", ".join(f.origin))
    if f.hs_prefix:
        parts.append("HS " + ", ".join(f.hs_prefix))
    if f.office:
        parts.append("office " + ", ".join((offices or {}).get(o, o) for o in f.office))
    if f.importer:
        parts.append(f"importer {f.importer}")
    if f.date_from or f.date_to:
        parts.append(f"dates {f.date_from or '…'} → {f.date_to or '…'}")
    parts.append({"fraud_desc": "sorted by fraud risk", "critical_desc": "sorted by safety risk",
                  "date_desc": "most recent first"}[f.sort])
    parts.append(f"top {f.limit}")
    return " · ".join(parts)


def parse(q: str, vocab: Vocab, use_llm: bool = True, mode: str = "hybrid") -> dict:
    """mode: "hybrid" (default: the rule parser when it recognises the question - measured more exact on our test
    set - otherwise Qwen for free phrasing), "llm" (Qwen only), "rules" (rules only)."""
    q = (q or "").strip()[:300]
    source = "rules"
    raw: dict = {}
    warnings: list[str] = []
    rules = rules_parse(q, vocab) if mode != "llm" else {}
    if mode == "rules" or (mode == "hybrid" and rules):
        f, w = validate(rules, vocab)
        return {"filter": f.model_dump(), "source": "rules", "warnings": w, "explanation": explain(f, vocab.offices),
                "llm_fallback": None}
    llm_fallback = None
    if use_llm and not client.available() and client.enabled():
        llm_fallback = "unavailable"
        warnings.append(f"LLM local indisponible ({client.status()['last_error'] or 'not available'}); "
                        "used the rule-based parser")
    elif use_llm and client.available():
        try:
            content, _ = client.chat(_system_prompt(vocab), f"Question: {q}", schema=SCHEMA, temperature=0.0,
                                     num_predict=200)
            raw = json.loads(content)
            source = "qwen3-4b"
            if raw.get("sort") == "critical_desc" and not raw.get("safety_only"):
                raw["sort"] = "fraud_desc"  # a safety ordering only makes sense for a safety question
        except (client.LLMError, ValueError) as exc:
            warnings.append(f"LLM unavailable ({exc}); used the rule-based parser")
            llm_fallback = "unavailable" if isinstance(exc, client.LLMError) else "rejected"
            raw = {}
    if source == "rules":
        raw = rules_parse(q, vocab)
    f, w = validate(raw, vocab)
    return {"filter": f.model_dump(), "source": source, "warnings": warnings + w,
            "explanation": explain(f, vocab.offices), "llm_fallback": llm_fallback}
