"""Officer brief: 4 sentences in French, English or Arabic, built ONLY from computed facts.

Deterministic templates (no LLM): every number comes from the facts dict, so nothing can be
invented. An LLM rewrite can be plugged in later behind the same endpoint (not enabled: no key).
"""
from __future__ import annotations

LANGS = ("fr", "en", "ar")

ROLE = {
    "fr": {"product": "le produit", "family": "la famille de produits", "chapter": "le chapitre SH",
           "importer": "l'importateur", "declarant": "le déclarant", "seller": "le vendeur",
           "origin": "l'origine", "office": "le bureau"},
    "en": {"product": "product", "family": "product family", "chapter": "HS chapter", "importer": "importer",
           "declarant": "declarant", "seller": "seller", "origin": "origin", "office": "customs office"},
    "ar": {"product": "المنتج", "family": "عائلة المنتجات", "chapter": "الفصل", "importer": "المستورد",
           "declarant": "المصرّح", "seller": "البائع", "origin": "بلد المنشأ", "office": "المكتب الديواني"},
}
REC = {
    "fr": {"RED": "Recommandation : inspection physique (voie rouge).",
           "YELLOW": "Recommandation : contrôle documentaire (voie jaune).",
           "GREEN": "Recommandation : mainlevée (voie verte)."},
    "en": {"RED": "Recommendation: physical inspection (red lane).",
           "YELLOW": "Recommendation: document check (yellow lane).",
           "GREEN": "Recommendation: release (green lane)."},
    "ar": {"RED": "التوصية: تفتيش مادي (المسار الأحمر).",
           "YELLOW": "التوصية: مراقبة وثائقية (المسار الأصفر).",
           "GREEN": "التوصية: رفع اليد (المسار الأخضر)."},
}


def _pct(x: float, lang: str, digits: int = 0) -> str:
    s = f"{x * 100:.{digits}f}"
    if lang == "fr":
        return s.replace(".", ",") + " %"
    return s + "%"


def _num(n: int, lang: str) -> str:
    return f"{n:,}".replace(",", " " if lang == "fr" else ",")


def _reason(f: dict, lang: str) -> str:
    r = f.get("top")
    if not r:
        return ""
    up = r["direction"] == "raises"
    g = r["group"]
    lead = {"fr": f"Facteur le plus influent ({'augmente' if up else 'réduit'} le risque) : ",
            "en": f"Strongest factor ({'raises' if up else 'lowers'} the risk): ",
            "ar": f"العامل الأكثر تأثيرًا ({'يرفع' if up else 'يخفض'} الخطر): "}[lang]
    if g in ROLE[lang]:
        role, code, n = ROLE[lang][g], r.get("code") or "", int(r.get("count") or 0)
        if n == 0 or r.get("rate") is None:
            body = {"fr": f"{role} {code} sans historique (traité comme risque moyen).",
                    "en": f"{role} {code} with no history (treated as average risk).",
                    "ar": f"{role} {code} بدون سوابق (يُعامل كخطر متوسط)."}[lang]
        else:
            rate, avg = _pct(r["rate"], lang), _pct(f["avg_fraud"], lang)
            if g == "product":
                body = {"fr": f"le produit {code} a été frauduleux dans {rate} de ses {_num(n, lang)} déclarations passées (moyenne {avg}).",
                        "en": f"product {code} was fraudulent in {rate} of its {_num(n, lang)} past declarations (average {avg}).",
                        "ar": f"المنتج {code} كان مغشوشًا في {rate} من تصاريحه السابقة البالغ عددها {_num(n, lang)} (المعدل {avg})."}[lang]
            else:
                body = {"fr": f"{role} {code} : {rate} de fraude sur {_num(n, lang)} déclarations passées (moyenne {avg}).",
                        "en": f"{role} {code}: {rate} fraud on {_num(n, lang)} past declarations (average {avg}).",
                        "ar": f"{role} {code}: نسبة غش {rate} على {_num(n, lang)} تصريحًا سابقًا (المعدل {avg})."}[lang]
    elif g == "tax":
        tax = f"{r.get('tax', 0):g}".replace(".", "," if lang == "fr" else ".")
        body = {"fr": f"le taux de droit ({tax} %).", "en": f"the tax rate ({tax}%).",
                "ar": f"نسبة المعلوم الديواني ({tax}%)."}[lang]
    elif g == "value":
        body = {"fr": "la valeur et la masse déclarées.", "en": "the declared value and mass.",
                "ar": "القيمة والكتلة المصرّح بهما."}[lang]
    else:
        body = {"fr": "une combinaison de facteurs (terme d'interaction du modèle transparent).",
                "en": "a combination of factors (interaction term of the glass-box model).",
                "ar": "تركيبة من عدة عوامل (حدّ تفاعل في النموذج الشفاف)."}[lang]
    return lead + body


def template_brief(f: dict, lang: str = "fr") -> str:
    lang = lang if lang in LANGS else "fr"
    fp = f["fraud_percentile"]
    pctl = f"{min(fp, 99.9):.1f}" if fp >= 99 else f"{fp:.0f}"
    if lang == "fr":
        pctl = pctl.replace(".", ",")
    p, pc = _pct(f["p_fraud"], lang), _pct(f["p_critical"], lang, 1)
    s1 = REC[lang][f["lane"]] + {
        "fr": f" Risque de fraude douanière estimé à {p} (au-dessus de {pctl} % des déclarations de la période).",
        "en": f" Estimated duty-fraud risk {p} (above {pctl}% of the period's declarations).",
        "ar": f" خطر الغش الجمركي المقدّر {p} (أعلى من {pctl}% من تصاريح الفترة).",
    }[lang]
    s2 = _reason(f, lang)
    if f["alert"]:
        s3 = {"fr": f"Alerte sécurité publique : risque de fraude critique de {pc} (top 1 %).",
              "en": f"Public-safety alert: critical-fraud risk {pc} (top 1%).",
              "ar": f"تنبيه للسلامة العامة: خطر غش خطير بنسبة {pc} (ضمن أعلى 1%)."}[lang]
    else:
        s3 = {"fr": f"Risque pour la sécurité publique : {pc}, sans alerte.",
              "en": f"Public-safety risk: {pc}, no alert.",
              "ar": f"خطر على السلامة العامة: {pc} دون تنبيه."}[lang]
    rule_inspects = f["rule_decision"] == "INSPECT"
    s4 = {"fr": ("La règle actuelle (historique du produit) " + ("l'aurait aussi inspectée" if rule_inspects else "ne l'aurait pas inspectée")
                 + ("; les deux modèles divergent : revue humaine requise" if f["uncertain"] else "")
                 + ". Décision finale : l'agent des douanes."),
          "en": ("The current rule (product history) " + ("would also inspect it" if rule_inspects else "would not inspect it")
                 + ("; the two models disagree: human review required" if f["uncertain"] else "")
                 + ". Final decision: the customs officer."),
          "ar": ("القاعدة الحالية (سوابق المنتج) " + ("كانت ستفتشه أيضًا" if rule_inspects else "لم تكن لتفتشه")
                 + ("؛ النموذجان مختلفان: مراجعة بشرية ضرورية" if f["uncertain"] else "")
                 + ". القرار النهائي للعون الديواني.")}[lang]
    return " ".join(s for s in (s1, s2, s3, s4) if s)
