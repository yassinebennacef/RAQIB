"""Measure the optional local LLM -> artifacts/llm_eval.json.

- NLQ: tests/data/nlq_cases.json (30 questions FR/EN/AR): exact-match and field-level accuracy, for Qwen and for
  the rule-based fallback separately.
- Brief: 50 declarations in FR + 10 in AR + 10 in EN: guard pass rate, fallback rate, latency p50/p95.
If Ollama is off, writes {"skipped": true} for the LLM parts (the rules part is always measured).
Usage: .venv/Scripts/python scripts/eval_llm.py [--briefs 50]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from raqib import config as C  # noqa: E402
from raqib.llm import brief as LB  # noqa: E402
from raqib.llm import client  # noqa: E402
from raqib.llm.nlq import NLQFilter, parse  # noqa: E402

FIELDS = list(NLQFilter.model_fields)


def norm(d: dict) -> dict:
    base = NLQFilter().model_dump()
    out = {**base, **d}
    for k in ("lane", "origin", "hs_prefix", "office"):
        out[k] = sorted(out[k]) if out[k] else None
    if out["min_fraud"] is not None:
        out["min_fraud"] = round(float(out["min_fraud"]), 3)
    return out


def score_nlq(cases: list[dict], vocab, use_llm: bool, mode: str = "hybrid") -> dict:
    exact, fields, per_lang, rows = 0, 0, {}, []
    t0 = time.time()
    for c in cases:
        r = parse(c["q"], vocab, use_llm=use_llm, mode=mode)
        got, exp = norm(r["filter"]), norm(c["expected"])
        ok_fields = sum(got[f] == exp[f] for f in FIELDS)
        is_exact = ok_fields == len(FIELDS)
        exact += is_exact
        fields += ok_fields
        pl = per_lang.setdefault(c["lang"], [0, 0])
        pl[0] += is_exact
        pl[1] += 1
        rows.append({"q": c["q"], "source": r["source"], "exact": is_exact,
                     "wrong_fields": [f for f in FIELDS if got[f] != exp[f]]})
    n = len(cases)
    return {"n": n, "exact_match": exact / n, "field_accuracy": fields / (n * len(FIELDS)),
            "by_lang": {k: v[0] / v[1] for k, v in per_lang.items()},
            "tricky_exact": sum(r["exact"] for r, c in zip(rows, cases) if c.get("tricky")) / max(1, sum(1 for c in cases if c.get("tricky"))),
            "seconds": round(time.time() - t0, 1), "cases": rows}


REFUSAL_MARKERS = ["ne trouve pas", "cannot find", "can't find", "don't find", "do not find", "لا أجد", "ne figure pas",
                   "pas dans la base", "not in the knowledge base"]


def eval_assistant() -> dict:
    from raqib.api import AssistantRequest, assistant
    client.warm_up()
    cases = json.loads((ROOT / "tests" / "data" / "assistant_cases.json").read_text(encoding="utf-8"))
    rows = []
    for c in cases:
        t0 = time.time()
        r = assistant(AssistantRequest(messages=[{"role": "user", "content": c["q"]}], lang=c["lang"], page=c["page"]))
        refused = r["source"] == "faq" and bool(r.get("out_of_scope")) or any(m in r["answer"].lower() for m in REFUSAL_MARKERS)
        rows.append({"q": c["q"], "lang": c["lang"], "source": r["source"], "guard_passed": r["guard_passed"],
                     "latency_ms": int((time.time() - t0) * 1000), "out_of_scope": bool(c.get("out_of_scope")),
                     "refused": refused, "answer": r["answer"][:300]})
    ins = [r for r in rows if not r["out_of_scope"]]
    oos = [r for r in rows if r["out_of_scope"]]
    lat = np.array([r["latency_ms"] for r in ins])
    return {"n": len(rows), "in_scope_n": len(ins), "guard_pass_rate": float(np.mean([r["guard_passed"] for r in ins])),
            "fallback_rate": float(np.mean([r["source"] == "faq" for r in ins])),
            "latency_ms_p50": int(np.percentile(lat, 50)), "latency_ms_p95": int(np.percentile(lat, 95)),
            "out_of_scope_n": len(oos), "out_of_scope_refused": int(sum(r["refused"] for r in oos)),
            "in_scope_wrongly_refused": int(sum(r["refused"] for r in ins)), "cases": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefs", type=int, default=50)
    ap.add_argument("--skip-briefs", action="store_true", help="re-measure NLQ only, keep the previous brief results")
    ap.add_argument("--assistant-only", action="store_true", help="measure the assistant only, keep the other results")
    args = ap.parse_args()
    from raqib.api import _llm_brief_inputs, _nlq_vocab, worklist
    from raqib.brief import template_brief

    vocab = _nlq_vocab()
    if args.assistant_only:
        client.refresh_status()
        prev = json.loads((C.ARTIFACTS / "llm_eval.json").read_text(encoding="utf-8")) if (C.ARTIFACTS / "llm_eval.json").exists() else {}
        prev["assistant"] = eval_assistant()
        (C.ARTIFACTS / "llm_eval.json").write_text(json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")
        a = prev["assistant"]
        print(f"Assistant: guard pass {a['guard_pass_rate']:.0%} (in scope), fallback {a['fallback_rate']:.0%}, "
              f"out-of-scope refused {a['out_of_scope_refused']}/{a['out_of_scope_n']}, p50 {a['latency_ms_p50']} ms, p95 {a['latency_ms_p95']} ms")
        return
    cases = json.loads((ROOT / "tests" / "data" / "nlq_cases.json").read_text(encoding="utf-8"))
    client.refresh_status()
    out: dict = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "model": client.status()["model"], "nlq": {"rules": score_nlq(cases, vocab, use_llm=False, mode="rules")}}
    if not client.available():
        out.update({"skipped": True, "reason": "Ollama not reachable: LLM parts skipped"})
    else:
        client.warm_up()
        out["nlq"]["qwen"] = score_nlq(cases, vocab, use_llm=True, mode="llm")
        out["nlq"]["hybrid"] = score_nlq(cases, vocab, use_llm=True, mode="hybrid")
        out["nlq"]["note"] = ("The rule parser was written alongside these 30 questions, so its score is optimistic; "
                              "Qwen handles free phrasings the rules do not know (hybrid = rules first, then Qwen).")
        if args.skip_briefs:
            prev = json.loads((C.ARTIFACTS / "llm_eval.json").read_text(encoding="utf-8"))
            if "brief" in prev:
                out["brief"] = prev["brief"]
            (C.ARTIFACTS / "llm_eval.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            print({k: (round(v["exact_match"], 3), round(v["field_accuracy"], 3)) for k, v in out["nlq"].items() if isinstance(v, dict)})
            return
        rng = np.random.default_rng(0)
        items = worklist(page_size=500, sort="p_fraud")["items"]
        ids = [items[i]["id"] for i in sorted(rng.choice(len(items), size=min(args.briefs, len(items)), replace=False))]
        jobs = [(i, "fr") for i in ids] + [(i, "ar") for i in ids[:10]] + [(i, "en") for i in ids[:10]]
        res = []
        for decl_id, lang in jobs:
            facts, tfacts = _llm_brief_inputs(decl_id)
            t0 = time.time()
            b = LB.brief(decl_id, lang, facts, template_brief(tfacts, lang), refresh=True)
            res.append({"id": decl_id, "lang": lang, "source": b["source"], "guard_passed": b["guard_passed"],
                        "latency_ms": int((time.time() - t0) * 1000), "rejected": b.get("rejected", [])})
        lat = np.array([r["latency_ms"] for r in res])
        by = {}
        for lang in ("fr", "ar", "en"):
            rr = [r for r in res if r["lang"] == lang]
            by[lang] = {"n": len(rr), "guard_pass_rate": float(np.mean([r["guard_passed"] for r in rr])) if rr else None}
        out["brief"] = {"n": len(res), "guard_pass_rate": float(np.mean([r["guard_passed"] for r in res])),
                        "fallback_rate": float(np.mean([r["source"] == "template" for r in res])),
                        "latency_ms_p50": int(np.percentile(lat, 50)), "latency_ms_p95": int(np.percentile(lat, 95)),
                        "by_lang": by, "rejections": [r for r in res if not r["guard_passed"]][:15]}
    (C.ARTIFACTS / "llm_eval.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    rules = out["nlq"]["rules"]
    print(f"NLQ rules: exact {rules['exact_match']:.0%}, fields {rules['field_accuracy']:.0%}")
    if "qwen" in out["nlq"]:
        q = out["nlq"]["qwen"]
        print(f"NLQ qwen:  exact {q['exact_match']:.0%}, fields {q['field_accuracy']:.0%} ({q['seconds']}s)")
    if "brief" in out:
        b = out["brief"]
        print(f"Brief: guard pass {b['guard_pass_rate']:.0%}, fallback {b['fallback_rate']:.0%}, "
              f"p50 {b['latency_ms_p50']} ms, p95 {b['latency_ms_p95']} ms, by lang {b['by_lang']}")


if __name__ == "__main__":
    main()
