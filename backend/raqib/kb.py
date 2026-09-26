"""`python -m raqib.kb` - write docs/assistant_kb.md, the knowledge base of the "Assistant RAQIB".

Every number is computed from the artifacts (metrics.json, data_card.json, efficiency, experiments), like the other
generated docs. Format per section:
    ## <key> | <title>
    keywords: fr, en, ar words ...
    page: /route
    <text>
"""
from __future__ import annotations

from . import config as C
from .report import V, num, pct, pts


def sections(v: V) -> list[tuple[str, str, str, str, str]]:
    c, m = v.c, v.m
    fe, fl, ke, kl = v.fm["ebm"], v.fm["lightgbm"], v.km["ebm"], v.km["lightgbm"]
    mt, pl, oh = v.eff["matching"], v.eff["pooled"], v.eff["officer_hours"]
    u = v.unc
    ex = {e["key"]: e["result"] for e in v.exps}
    th = v.th
    gf, gk = v.F["gain_vs_rule"], v.K["gain_vs_rule"]
    return [
        ("overview", "Qu'est-ce que RAQIB", "raqib, projet, objectif, what, overview, but, رقيب", "/about",
         "RAQIB (« رقيب », le surveillant) aide la douane à choisir quelles déclarations d'importation inspecter "
         "physiquement quand la capacité d'inspection est limitée. Il classe chaque déclaration selon deux risques "
         "(fraude douanière et fraude critique pour la sécurité publique), propose une voie et explique pourquoi. "
         "L'agent des douanes décide toujours."),
        ("lanes", "Les trois voies : ROUGE, JAUNE, VERTE", "voie, voies, lane, lanes, trois, three, rouge, jaune, vert, red, yellow, green, المسار, المسارات, الثلاثة, أحمر, أصفر, أخضر", "/worklist",
         "ROUGE = inspection physique, JAUNE = contrôle documentaire, VERTE = mainlevée (libération). "
         f"Sur la période de test, l'IA envoie {pct(v.ai['green_share'])} des déclarations en voie verte."),
        ("why_red", "Pourquoi une déclaration est ROUGE", "pourquoi, rouge, red, why, inspection, capacité, top, لماذا, أحمر", "/declaration",
         "Une déclaration passe en ROUGE si elle fait partie des déclarations les plus risquées du jour dans la limite "
         "de la capacité (5 % par jour), ou si son risque pour la sécurité publique est dans le top 1 % (alerte "
         f"sécurité, prioritaire). Seuils : risque de fraude au moins {pct(th['red_p_fraud'], 1)} pour ROUGE, "
         f"{pct(th['yellow_p_fraud'], 1)} pour JAUNE, risque critique au moins {pct(th['alert_p_critical'], 1)} pour l'alerte."),
        ("capacity", "La capacité d'inspection quotidienne", "capacité, capacity, 5%, quota, inspections par jour, السعة", "/",
         "La douane ne peut inspecter qu'une petite part des déclarations. RAQIB travaille avec une capacité fixe : "
         f"5 % des déclarations de chaque jour, soit {num(v.rs['totals']['inspections'])} inspections sur les "
         f"{v.rs['n_days']} jours de test, identique pour l'IA, la règle et le hasard."),
        ("allocation", "Comment RAQIB choisit les contrôles", "choisir, choisit, allocation, sélection, choose, select, how, كيف, اختيار", "/",
         "Chaque jour : 1) les alertes sécurité publique prennent d'abord des places d'inspection ; 2) les places "
         "restantes vont aux risques de fraude les plus élevés ; 3) en option, 10 % des places sont tirées au hasard "
         "(exploration). Séparément, les déclarations classées juste après les inspections (les 10 % suivants de la journée) "
         "passent en JAUNE (contrôle documentaire) ; toutes les autres passent en VERT."),
        ("exploration", "L'exploration (10 %)", "exploration, hasard, random, aléatoire, explore, apprentissage, استكشاف", "/",
         f"Une petite part des inspections est tirée au hasard pour que le système continue d'apprendre sur des produits "
         f"qu'il ne choisirait jamais. Sur la période de test, elle coûte {num(v.ai['frauds'] - v.aie['frauds'])} fraudes "
         f"mais élargit la couverture de {num(v.ai['distinct_hs6'])} à {num(v.aie['distinct_hs6'])} produits différents."),
        ("safety", "L'alerte sécurité publique", "sécurité, securite, safety, alerte, alert, critique, critical, menace, danger, أمن, تنبيه, السلامة", "/lab",
         "La fraude critique correspond à une infraction grave (par exemple des marchandises dangereuses). Les "
         f"déclarations dont le risque critique est dans le top 1 % sont inspectées en priorité. RAQIB attrape "
         f"{num(v.ai['threats'])} menaces contre {num(v.rule['threats'])} pour la règle actuelle, avec les mêmes inspections."),
        ("two_models", "Les deux familles de modèles", "modèle, modèles, model, ebm, lightgbm, deux, twin, jumeau, نموذج", "/explainability",
         "Chaque risque est estimé par deux modèles : une Explainable Boosting Machine (EBM, boîte de verre) et un "
         "LightGBM (gradient boosting). Le modèle principal est l'EBM pour la fraude douanière et LightGBM pour la "
         "sécurité publique. Leur désaccord sert d'alerte d'incertitude."),
        ("ebm", "L'EBM, une boîte de verre", "ebm, boîte de verre, glass box, transparent, explicable, interpretable, شفاف", "/explainability",
         "L'EBM est un modèle additif : chaque probabilité est la somme exacte de contributions lisibles, une par "
         f"facteur, et on peut afficher la courbe apprise pour chaque facteur. Pour la fraude douanière il atteint une "
         f"AUC de {fe['auc']:.3f} et une précision à 5 % de {pct(fe['precision_at_5'], 1)}, contre {fl['auc']:.3f} et "
         f"{pct(fl['precision_at_5'], 1)} pour LightGBM : aucune perte de précision."),
        ("primary_rule", "Quel modèle est principal", "principal, primary, règle, choix du modèle, 1.5 points", "/model-card",
         "L'EBM devient principal si sa métrique opérationnelle est à moins de 1,5 point de LightGBM ou meilleure. "
         f"Fraude : EBM {pct(fe['precision_at_5'], 1)} contre {pct(fl['precision_at_5'], 1)}, donc EBM principal. "
         f"Sécurité : rappel à 5 % de l'EBM {pct(ke['recall_at_5'], 1)} contre {pct(kl['recall_at_5'], 1)}, donc LightGBM principal."),
        ("calibration", "La calibration des probabilités", "calibration, calibré, probabilité, probability, fiable", "/lab",
         "Une probabilité de 60 % doit correspondre à environ 60 % de fraudes observées. Dans le dixième le plus risqué, "
         f"le modèle prévoit {pct(v.cal_top['mean_predicted'], 1)} et on observe {pct(v.cal_top['observed'], 1)}."),
        ("disagreement", "Le désaccord des modèles", "désaccord, desaccord, incertain, uncertain, disagree, disagreement, models disagree, اختلاف, غير مؤكد", "/worklist",
         "Quand l'EBM et LightGBM donnent des risques de fraude très différents (écart au-dessus du 95e centile mesuré "
         "hors échantillon sur les 4 dernières semaines d'entraînement), la déclaration est marquée « modèles en "
         f"désaccord » et n'est jamais libérée en vert : un humain regarde. Sur la période de test : {num(u['n_flagged'])} "
         f"déclarations, avec un taux de fraude de {pct(u['fraud_rate_flagged'])} contre {pct(u['fraud_rate_all'])} en moyenne."),
        ("reasons", "Les 4 raisons d'une déclaration", "raison, raisons, pourquoi, reasons, why, facteur, facteurs, أسباب", "/declaration",
         "Pour chaque déclaration, RAQIB affiche les 4 facteurs qui pèsent le plus (historique du produit, de "
         "l'importateur, du déclarant, du vendeur, origine, bureau, taxe, valeur et masse), avec les vrais chiffres "
         "historiques, par exemple le taux de fraude passé du produit et le nombre de déclarations passées."),
        ("waterfall", "La cascade exacte (waterfall)", "cascade, waterfall, contribution, décomposition, étape", "/declaration",
         "La cascade part du taux de base du modèle et ajoute, facteur par facteur, sa contribution exacte jusqu'à la "
         "probabilité finale. Rouge augmente le risque, vert le diminue. La somme est exacte, rien n'est approximé."),
        ("rule", "La règle actuelle (historique du produit)", "règle, regle, rule, actuelle, current, historique produit, القاعدة", "/declaration",
         "La règle de comparaison inspecte chaque jour les déclarations dont le produit (code SH6) a le taux de fraude "
         f"passé le plus élevé. C'est la meilleure règle simple testée : précision à 5 % de "
         f"{pct(v.fm['rule_hs6_history']['precision_at_5'], 1)}. Chaque déclaration montre ce que la règle aurait décidé."),
        ("history_features", "Comment l'historique est utilisé", "historique, history, encodage, taux passé, hors échantillon, out-of-fold", "/about",
         "Pour le produit, la famille, le chapitre, l'importateur, le déclarant, le vendeur, l'origine et le bureau, "
         "RAQIB calcule le taux de fraude passé lissé et le volume, en « hors échantillon » : une déclaration "
         "d'entraînement ne voit jamais sa propre réponse."),
        ("auc", "Que signifie l'AUC", "auc, roc, qualité du classement, ranking", "/lab",
         "L'AUC mesure la qualité du classement sur tous les seuils : 0,5 = hasard, 1 = parfait. Fraude : "
         f"{v.fm['ai']['auc']:.3f} pour RAQIB contre {v.fm['rule_hs6_history']['auc']:.3f} pour la règle. Sécurité : "
         f"{v.km['ai']['auc']:.3f} contre {v.km['rule_hs6_history']['auc']:.3f}."),
        ("precision5", "Que signifie précision à 5 %", "précision, precision, 5%, top 5, taux de réussite, hit rate, دقة", "/lab",
         "La précision à 5 % est la part des 5 % de déclarations les plus risquées qui étaient vraiment frauduleuses. "
         f"RAQIB : {pct(v.fm['ai']['precision_at_5'], 1)}, règle : {pct(v.fm['rule_hs6_history']['precision_at_5'], 1)}, "
         f"hasard : {pct(v.fm['random']['precision_at_5'], 1)}."),
        ("recall5", "Que signifie rappel à 5 %", "rappel, recall, 5%, couverture, menaces trouvées", "/lab",
         "Le rappel à 5 % est la part de tous les cas positifs trouvés en inspectant les 5 % les plus risqués. Sécurité "
         f"publique : {pct(v.km['ai']['recall_at_5'], 1)} pour RAQIB contre {pct(v.km['rule_hs6_history']['recall_at_5'], 1)} "
         f"pour la règle, sur seulement {m['n_critical_test']} cas critiques."),
        ("ci", "Le gain est-il dû au hasard", "hasard, chance, luck, intervalle, confiance, bootstrap, significatif", "/lab",
         f"Le gain de précision à 5 % sur la règle est de {pts(gf['mean_gain'])} avec un intervalle de confiance à 95 % "
         f"de {pts(gf['ci95'][0])} à {pts(gf['ci95'][1])} (bootstrap) ; pour la sécurité, {pts(gk['mean_gain'])}. "
         f"L'IA bat la règle {v.weeks_better} semaines sur {v.n_weeks}."),
        ("replay", "Le rejeu des 91 jours", "rejeu, replay, course, race, jours, résultats, results, 317, salle de contrôle", "/",
         f"Sur {v.rs['n_days']} jours réels jamais vus à l'entraînement, avec {num(v.rs['totals']['inspections'])} inspections "
         f"pour chaque politique : RAQIB trouve {num(v.ai['frauds'])} fraudes et {num(v.ai['threats'])} menaces, la règle "
         f"{num(v.rule['frauds'])} et {num(v.rule['threats'])}, le hasard {num(v.rnd['frauds'])} et {num(v.rnd['threats'])}."),
        ("efficiency", "Les mêmes fraudes avec moins d'inspections", "efficacité, efficiency, moins d'inspections, fewer, impact, gain, économie", "/impact",
         f"La règle a besoin de {num(mt['reference']['inspections'])} inspections pour trouver {num(mt['reference']['frauds'])} "
         f"fraudes ; RAQIB en trouve {num(mt['ai_frauds'])} avec {num(mt['ai_inspections'])}, soit {pct(mt['fewer_pct'])} "
         f"d'inspections en moins (classement global : {pct(pl['fewer_pct'])} en moins)."),
        ("officer_hours", "Les heures d'agents libérées", "heures, hours, agents, temps, officers, économie de temps", "/impact",
         f"Avec l'hypothèse (modifiable) de {oh['minutes_per_inspection']:g} minutes par inspection, les inspections évitées "
         f"représentent {num(oh['hours_freed_test_period'])} heures sur la période, environ {num(oh['hours_freed_per_year'])} "
         "heures par an. C'est une hypothèse, pas une mesure."),
        ("fairness", "L'équité : qui est inspecté", "équité, fairness, biais, bias, discrimination, bureau, transport", "/lab",
         "RAQIB mesure le taux de sélection par bureau et par mode de transport. Rapport max/min : "
         f"{v.fair['office']['max_min_selection_ratio_ai']:.1f} entre bureaux, {v.fair['transport']['max_min_selection_ratio_ai']:.1f} "
         "entre modes de transport. Ces écarts sont suivis chaque semaine en production."),
        ("data", "D'où viennent les données", "données, data, source, dataset, corée, korea, synthétique, bacuda, بيانات", "/about",
         f"Jeu de données public « Customs Import Declaration Datasets » (Institute for Basic Science et Korea Customs "
         f"Service, licence MIT) : {num(c['rows'])} déclarations synthétiques issues de déclarations réellement "
         f"inspectées. Entraînement : {num(c['train']['rows'])} déclarations ; test : {num(c['test']['rows'])}. Aucune "
         "donnée tunisienne, aucun accès à un système de l'administration."),
        ("limits", "Les limites", "limites, limits, faiblesses, weakness, honnête, synthétique", "/lab",
         f"Seules des déclarations inspectées ont été synthétisées : le taux de fraude ({pct(c['fraud_rate'], 1)}) est "
         f"bien plus élevé que dans la réalité ; on revendique le gain sur la règle, pas la précision absolue. Seulement "
         f"{m['n_critical_test']} cas critiques dans le test. Les seuils des voies sont fixés sur la période de test."),
        ("new_operators", "Les nouveaux opérateurs", "nouveau, nouvel, new, importateur inconnu, sans historique, no history", "/score",
         f"{pct(c['test_new_operators']['importer'])} des déclarations de test viennent d'importateurs jamais vus. Sans "
         "historique, ils sont traités comme un risque moyen et la raison l'indique."),
        ("tested", "Idées testées et rejetées", "testé, rejeté, tested, rejected, anomalie, anomaly, réseau, network, graphe, isolation forest", "/explainability",
         f"Détection d'anomalies (Isolation Forest) : AUC {ex['isolation_forest']['fraud_auc']:.2f}, aucun signal, rejetée. "
         f"Variables de réseau à 2 sauts : AUC {ex['network_2hop']['auc_with']:.4f} contre "
         f"{ex['network_2hop']['auc_without']:.4f} sans, aucun gain, rejetées (les lignes synthétiques n'ont pas de vrais liens)."),
        ("journal", "Le journal des décisions (SHA-256)", "journal, décision, decision, hash, sha-256, chaîne, audit, traçabilité, سجل", "/journal",
         "Chaque décision de l'agent (inspecter, contrôle documentaire, libérer) est ajoutée à un journal chaîné : le "
         "hash SHA-256 de chaque ligne inclut celui de la précédente. Modifier, supprimer ou réordonner une ligne casse "
         "la chaîne ; le bouton « Verify chain » le vérifie."),
        ("human", "Qui décide", "décide, decide, agent, humain, human, officier, responsabilité, القرار", "/declaration",
         "RAQIB donne un score consultatif et des raisons ; l'agent des douanes décide toujours. Les déclarations où les "
         "modèles sont en désaccord sont signalées pour une revue humaine."),
        ("local_llm", "Le modèle de langage local", "llm, qwen, assistant, local, hors ligne, offline, ollama, intelligence artificielle générative", "/model-card",
         "Qwen3-4B tourne localement sur l'ordinateur via Ollama, sans internet : aucune donnée ne sort. Il ne note et ne "
         "décide rien : il reformule des faits déjà calculés (chaque nombre est vérifié) et traduit une question en filtre "
         "que l'agent valide."),
        ("brief", "Le brief de l'agent", "brief, résumé, synthèse, français, arabe, anglais", "/declaration",
         "Le brief résume en français, arabe ou anglais les faits calculés d'une déclaration : voie, probabilités, "
         "raisons, décision de la règle. Tout nombre absent des faits fait rejeter le texte, qui est alors remplacé par "
         "un modèle de texte fixe."),
        ("ask", "Ask RAQIB : filtrer en langage naturel", "ask, filtre, filter, question, montre, show, recherche, اعرض", "/worklist",
         "Tapez une question comme « déclarations rouges d'origine CN au chapitre 85 au-dessus de 80% » : RAQIB la "
         "transforme en filtre (puces) que vous vérifiez, puis vous cliquez « Appliquer ». Rien n'est appliqué automatiquement."),
        ("what_if", "Le simulateur « what-if »", "what-if, simulateur, simulation, et si, changer, valeur, masse", "/explainability",
         "Réservé aux agents : on change la valeur, la masse, la taxe ou un opérateur et on voit le risque, la voie et "
         "la cascade bouger. Il n'est jamais montré aux déclarants."),
        ("page_control", "Page Salle de contrôle", "salle de contrôle, control room, accueil, course, jouer, play", "/",
         "Rejoue les 91 jours de test : curseur de capacité, exploration, vitesse, compteurs IA / règle / hasard, "
         "courbe cumulée et fil des déclarations du jour."),
        ("page_worklist", "Page Worklist", "worklist, liste, boîte de réception, inbox, tableau, filtres", "/worklist",
         "La boîte de réception de l'agent : chaque déclaration avec sa voie, les deux risques, l'accord des modèles, la "
         "raison principale et la décision de la règle ; filtres, tri, pagination, panneau latéral de décision."),
        ("page_explain", "Page Explainability", "explainability, explicabilité, courbes, shape, importance", "/explainability",
         "Boîte de verre contre boîte noire, ce que le modèle a appris (importances et courbes), une déclaration expliquée "
         "exactement, le simulateur what-if et les idées testées."),
        ("page_impact", "Page Impact simulator", "impact, simulateur, courbe de capacité, capacity curve", "/impact",
         "Courbe du nombre de fraudes et de menaces trouvées selon la capacité, pour l'IA, la règle et le hasard, et "
         "calcul des inspections et des heures économisées."),
        ("production", "Passage en production en Tunisie", "production, tunisie, tunisia, pilote, déploiement, deploy, تونس", "/about",
         "Réentraîner le même modèle dans l'administration sur les résultats d'inspection tunisiens, fonctionner 4 à 8 "
         "semaines en mode fantôme, puis un pilote avec un groupe témoin, et un suivi hebdomadaire (dérive, calibration, "
         "équité, désaccord)."),
    ]


def _fr(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def tunisia_sections() -> list[tuple[str, str, str, str, str]]:
    """Tunisian edition: currencies and real public Tunisian data (UN Comtrade), computed from the saved files."""
    from . import currency as CUR
    from . import tunisia as TN
    r = CUR.rates()
    out = [("currency", "Devises : TND, EUR, USD", "devise, devises, currency, dinar, tnd, euro, eur, dollar, usd, won, "
            "krw, taux, change, conversion, العملة, الدينار", "/about",
            f"Les valeurs du jeu public sont en wons coréens (KRW). RAQIB les convertit en dollars au taux moyen de la "
            f"période des données ({r['krw_period']} : 1 USD = {_fr(r['krw_per_usd'], 2)} KRW, source FRED), puis en "
            f"dinars et en euros aux taux de référence du {r['reference_date']} (1 EUR = {_fr(r['tnd_per_eur'], 4)} TND, "
            f"1 USD = {_fr(r['tnd_per_usd'], 4)} TND, countryeconomy.com). Le sélecteur TND | EUR | USD en haut de "
            "l'écran change l'affichage partout ; TND par défaut.")]
    t = TN.load()
    if not t:
        return out
    c = t.get("check") or {}
    top = t["top_origins"][:3]
    reported = [m for m in t["mirror"] if m["reported"] and m["gap"] is not None]
    out += [
        ("tunisia", "Contexte tunisien (UN Comtrade)", "tunisie, tunisia, tunisien, comtrade, importations, imports, "
         "origine, origines, chapitre, pays, partenaire, تونس, الواردات", "/tunisie",
         f"La page Contexte tunisien montre des données réelles publiques : {t['source']}. La Tunisie a importé "
         f"{_fr(t['total_imports_usd'] / 1e9)} milliards USD en {t['year']} ; premières origines : "
         + ", ".join(f"{o['name']} ({_fr(o['usd'] / 1e9, 2)} Md USD)" for o in top)
         + f" ; premier chapitre SH {t['top_chapters'][0]['hs2']} ({_fr(t['top_chapters'][0]['usd'] / 1e9, 2)} Md USD). "
         "Ces données servent d'information seulement : elles n'entrent jamais dans les modèles."),
        ("mirror", "Écart miroir", "écart, miroir, mirror, gap, sous-facturation, underinvoicing, partenaire, exportations, "
         "فجوة, المرآة", "/tunisie",
         "L'écart miroir compare les importations déclarées par la Tunisie aux exportations déclarées par le partenaire "
         "vers la Tunisie : (importations − exportations) ÷ exportations. C'est un indicateur reconnu de sous-facturation, "
         f"pas une preuve (importations CIF, exportations FOB). En {t['year']} : "
         + ", ".join(f"{m['name']} {'+' if m['gap'] >= 0 else '−'}{_fr(abs(m['gap']) * 100)} %" for m in reported[:5]) + "."),
    ]
    if c.get("RED"):
        out.append(("reference_price", "Prix de référence tunisien", "prix, référence, reference, valeur, kg, "
                    "sous-évaluation, undervaluation, carte, inspecteur, السعر", "/tunisie",
                    "La carte Référence tunisienne compare la valeur déclarée par kg à la valeur moyenne par kg des "
                    f"importations tunisiennes du même SH6 ({len(t['hs6_ref'])} références). Mesure honnête : "
                    f"{_fr(c['RED']['share_under'] * 100)} % des ROUGES et {_fr(c['GREEN']['share_under'] * 100)} % des "
                    "VERTS sont sous 50 % de la référence : le seuil ne sépare pas les voies, car les valeurs "
                    f"synthétiques du jeu public valent environ {_fr((c.get('median_ratio') or 0) * 100)} % des prix réels "
                    "(médiane). Information seulement, jamais utilisée par le modèle."))
    return out


def write() -> int:
    v = V()
    out = ["# Assistant RAQIB - base de connaissances", "",
           "*Générée par `python -m raqib.kb` à partir des artefacts mesurés (ne pas modifier à la main).*", ""]
    secs = sections(v) + tunisia_sections()
    for key, title, kw, page, text in secs:
        out += [f"## {key} | {title}", f"keywords: {kw}", f"page: {page}", text, ""]
    (C.ROOT / "docs" / "assistant_kb.md").write_text("\n".join(out), encoding="utf-8")
    return len(secs)


if __name__ == "__main__":
    print(f"[kb] docs/assistant_kb.md: {write()} sections")
