"""Guards for LLM text: every number must come from the facts; no accusatory claims."""
from __future__ import annotations

import json
import re

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NUM_RE = re.compile(r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d(?:[\d,.]*\d)?")
BANNED = [
    "is fraudulent", "are fraudulent", "is a fraud", "certainly", "definitely", "arrest", "sanction", "penalt",
    "est frauduleux", "est frauduleuse", "sont frauduleu", "certainement", "sans aucun doute", "arrêter", "arrestation",
    "بالتأكيد", "اعتقال", "عقوبة", "مغشوشة بالتأكيد",
]


def normalize(text: str) -> str:
    return text.translate(ARABIC_DIGITS).replace("٫", ".").replace("٬", ",")


def _interpretations(tok: str) -> set[float]:
    """A token like '1,200' or '71,8' or '1 200' can mean several numbers; return them all."""
    t = tok.replace(" ", "").replace(" ", "").replace(" ", "")
    out: set[float] = set()
    candidates = [t.replace(",", ""), t.replace(",", "."), t.replace(".", "").replace(",", ".")]
    for c in candidates:
        if c.count(".") <= 1:
            try:
                out.add(float(c))
            except ValueError:
                pass
    return out


def _decimals(tok: str) -> int:
    m = re.search(r"[.,](\d{1,2})$", tok)
    return len(m.group(1)) if m else 0


def numbers_in(text: str) -> list[str]:
    return NUM_RE.findall(normalize(text))


def fact_numbers(facts: dict) -> set[float]:
    vals: set[float] = set()
    for tok in numbers_in(json.dumps(facts, ensure_ascii=False)):
        vals |= _interpretations(tok)
    return vals


def unmatched_numbers(text: str, facts: dict, allow_small: int = 10) -> list[str]:
    """Numbers in `text` that cannot be traced to the facts (rounding and percent/fraction allowed)."""
    known = fact_numbers(facts)
    bad = []
    for tok in numbers_in(text):
        vals = _interpretations(tok)
        if any(v <= allow_small and float(v).is_integer() for v in vals):
            continue  # list numbering, "4 indicators"...
        tol = 0.5 * 10 ** (-_decimals(tok)) + 1e-9
        ok = any(abs(v - c) <= tol for v in vals for f in known for c in (f, f * 100, f / 100))
        if not ok:
            bad.append(tok)
    return bad


def banned_claims(text: str) -> list[str]:
    low = text.lower()
    return [b for b in BANNED if b in low]
