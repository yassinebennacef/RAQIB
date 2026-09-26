# Assistant RAQIB - base de connaissances

*Générée par `python -m raqib.kb` à partir des artefacts mesurés (ne pas modifier à la main).*

## overview | Qu'est-ce que RAQIB
keywords: raqib, projet, objectif, what, overview, but, رقيب
page: /about
RAQIB (« رقيب », le surveillant) aide la douane à choisir quelles déclarations d'importation inspecter physiquement quand la capacité d'inspection est limitée. Il classe chaque déclaration selon deux risques (fraude douanière et fraude critique pour la sécurité publique), propose une voie et explique pourquoi. L'agent des douanes décide toujours.

## lanes | Les trois voies : ROUGE, JAUNE, VERTE
keywords: voie, voies, lane, lanes, trois, three, rouge, jaune, vert, red, yellow, green, المسار, المسارات, الثلاثة, أحمر, أصفر, أخضر
page: /worklist
ROUGE = inspection physique, JAUNE = contrôle documentaire, VERTE = mainlevée (libération). Sur la période de test, l'IA envoie 82% des déclarations en voie verte.

## why_red | Pourquoi une déclaration est ROUGE
keywords: pourquoi, rouge, red, why, inspection, capacité, top, لماذا, أحمر
page: /declaration
Une déclaration passe en ROUGE si elle fait partie des déclarations les plus risquées du jour dans la limite de la capacité (5 % par jour), ou si son risque pour la sécurité publique est dans le top 1 % (alerte sécurité, prioritaire). Seuils : risque de fraude au moins 58.3% pour ROUGE, 38.6% pour JAUNE, risque critique au moins 14.2% pour l'alerte.

## capacity | La capacité d'inspection quotidienne
keywords: capacité, capacity, 5%, quota, inspections par jour, السعة
page: /
La douane ne peut inspecter qu'une petite part des déclarations. RAQIB travaille avec une capacité fixe : 5 % des déclarations de chaque jour, soit 470 inspections sur les 91 jours de test, identique pour l'IA, la règle et le hasard.

## allocation | Comment RAQIB choisit les contrôles
keywords: choisir, choisit, allocation, sélection, choose, select, how, كيف, اختيار
page: /
Chaque jour : 1) les alertes sécurité publique prennent d'abord des places d'inspection ; 2) les places restantes vont aux risques de fraude les plus élevés ; 3) en option, 10 % des places sont tirées au hasard (exploration). Séparément, les déclarations classées juste après les inspections (les 10 % suivants de la journée) passent en JAUNE (contrôle documentaire) ; toutes les autres passent en VERT.

## exploration | L'exploration (10 %)
keywords: exploration, hasard, random, aléatoire, explore, apprentissage, استكشاف
page: /
Une petite part des inspections est tirée au hasard pour que le système continue d'apprendre sur des produits qu'il ne choisirait jamais. Sur la période de test, elle coûte 23 fraudes mais élargit la couverture de 261 à 280 produits différents.

## safety | L'alerte sécurité publique
keywords: sécurité, securite, safety, alerte, alert, critique, critical, menace, danger, أمن, تنبيه, السلامة
page: /lab
La fraude critique correspond à une infraction grave (par exemple des marchandises dangereuses). Les déclarations dont le risque critique est dans le top 1 % sont inspectées en priorité. RAQIB attrape 41 menaces contre 7 pour la règle actuelle, avec les mêmes inspections.

## two_models | Les deux familles de modèles
keywords: modèle, modèles, model, ebm, lightgbm, deux, twin, jumeau, نموذج
page: /explainability
Chaque risque est estimé par deux modèles : une Explainable Boosting Machine (EBM, boîte de verre) et un LightGBM (gradient boosting). Le modèle principal est l'EBM pour la fraude douanière et LightGBM pour la sécurité publique. Leur désaccord sert d'alerte d'incertitude.

## ebm | L'EBM, une boîte de verre
keywords: ebm, boîte de verre, glass box, transparent, explicable, interpretable, شفاف
page: /explainability
L'EBM est un modèle additif : chaque probabilité est la somme exacte de contributions lisibles, une par facteur, et on peut afficher la courbe apprise pour chaque facteur. Pour la fraude douanière il atteint une AUC de 0.771 et une précision à 5 % de 71.8%, contre 0.770 et 71.1% pour LightGBM : aucune perte de précision.

## primary_rule | Quel modèle est principal
keywords: principal, primary, règle, choix du modèle, 1.5 points
page: /model-card
L'EBM devient principal si sa métrique opérationnelle est à moins de 1,5 point de LightGBM ou meilleure. Fraude : EBM 71.8% contre 71.1%, donc EBM principal. Sécurité : rappel à 5 % de l'EBM 67.1% contre 78.1%, donc LightGBM principal.

## calibration | La calibration des probabilités
keywords: calibration, calibré, probabilité, probability, fiable
page: /lab
Une probabilité de 60 % doit correspondre à environ 60 % de fraudes observées. Dans le dixième le plus risqué, le modèle prévoit 61.7% et on observe 61.4%.

## disagreement | Le désaccord des modèles
keywords: désaccord, desaccord, incertain, uncertain, disagree, disagreement, models disagree, اختلاف, غير مؤكد
page: /worklist
Quand l'EBM et LightGBM donnent des risques de fraude très différents (écart au-dessus du 95e centile mesuré hors échantillon sur les 4 dernières semaines d'entraînement), la déclaration est marquée « modèles en désaccord » et n'est jamais libérée en vert : un humain regarde. Sur la période de test : 371 déclarations, avec un taux de fraude de 44% contre 22% en moyenne.

## reasons | Les 4 raisons d'une déclaration
keywords: raison, raisons, pourquoi, reasons, why, facteur, facteurs, أسباب
page: /declaration
Pour chaque déclaration, RAQIB affiche les 4 facteurs qui pèsent le plus (historique du produit, de l'importateur, du déclarant, du vendeur, origine, bureau, taxe, valeur et masse), avec les vrais chiffres historiques, par exemple le taux de fraude passé du produit et le nombre de déclarations passées.

## waterfall | La cascade exacte (waterfall)
keywords: cascade, waterfall, contribution, décomposition, étape
page: /declaration
La cascade part du taux de base du modèle et ajoute, facteur par facteur, sa contribution exacte jusqu'à la probabilité finale. Rouge augmente le risque, vert le diminue. La somme est exacte, rien n'est approximé.

## rule | La règle actuelle (historique du produit)
keywords: règle, regle, rule, actuelle, current, historique produit, القاعدة
page: /declaration
La règle de comparaison inspecte chaque jour les déclarations dont le produit (code SH6) a le taux de fraude passé le plus élevé. C'est la meilleure règle simple testée : précision à 5 % de 53.4%. Chaque déclaration montre ce que la règle aurait décidé.

## history_features | Comment l'historique est utilisé
keywords: historique, history, encodage, taux passé, hors échantillon, out-of-fold
page: /about
Pour le produit, la famille, le chapitre, l'importateur, le déclarant, le vendeur, l'origine et le bureau, RAQIB calcule le taux de fraude passé lissé et le volume, en « hors échantillon » : une déclaration d'entraînement ne voit jamais sa propre réponse.

## auc | Que signifie l'AUC
keywords: auc, roc, qualité du classement, ranking
page: /lab
L'AUC mesure la qualité du classement sur tous les seuils : 0,5 = hasard, 1 = parfait. Fraude : 0.771 pour RAQIB contre 0.728 pour la règle. Sécurité : 0.952 contre 0.924.

## precision5 | Que signifie précision à 5 %
keywords: précision, precision, 5%, top 5, taux de réussite, hit rate, دقة
page: /lab
La précision à 5 % est la part des 5 % de déclarations les plus risquées qui étaient vraiment frauduleuses. RAQIB : 71.8%, règle : 53.4%, hasard : 21.4%.

## recall5 | Que signifie rappel à 5 %
keywords: rappel, recall, 5%, couverture, menaces trouvées
page: /lab
Le rappel à 5 % est la part de tous les cas positifs trouvés en inspectant les 5 % les plus risqués. Sécurité publique : 78.1% pour RAQIB contre 54.8% pour la règle, sur seulement 73 cas critiques.

## ci | Le gain est-il dû au hasard
keywords: hasard, chance, luck, intervalle, confiance, bootstrap, significatif
page: /lab
Le gain de précision à 5 % sur la règle est de +17.8 pts avec un intervalle de confiance à 95 % de +12.5 pts à +22.5 pts (bootstrap) ; pour la sécurité, +22.5 pts. L'IA bat la règle 12 semaines sur 13.

## replay | Le rejeu des 91 jours
keywords: rejeu, replay, course, race, jours, résultats, results, 317, salle de contrôle
page: /
Sur 91 jours réels jamais vus à l'entraînement, avec 470 inspections pour chaque politique : RAQIB trouve 317 fraudes et 41 menaces, la règle 259 et 7, le hasard 103 et 3.

## efficiency | Les mêmes fraudes avec moins d'inspections
keywords: efficacité, efficiency, moins d'inspections, fewer, impact, gain, économie
page: /impact
La règle a besoin de 470 inspections pour trouver 259 fraudes ; RAQIB en trouve 263 avec 379, soit 19% d'inspections en moins (classement global : 29% en moins).

## officer_hours | Les heures d'agents libérées
keywords: heures, hours, agents, temps, officers, économie de temps
page: /impact
Avec l'hypothèse (modifiable) de 60 minutes par inspection, les inspections évitées représentent 91 heures sur la période, environ 365 heures par an. C'est une hypothèse, pas une mesure.

## fairness | L'équité : qui est inspecté
keywords: équité, fairness, biais, bias, discrimination, bureau, transport
page: /lab
RAQIB mesure le taux de sélection par bureau et par mode de transport. Rapport max/min : 1.7 entre bureaux, 1.1 entre modes de transport. Ces écarts sont suivis chaque semaine en production.

## data | D'où viennent les données
keywords: données, data, source, dataset, corée, korea, synthétique, bacuda, بيانات
page: /about
Jeu de données public « Customs Import Declaration Datasets » (Institute for Basic Science et Korea Customs Service, licence MIT) : 54,000 déclarations synthétiques issues de déclarations réellement inspectées. Entraînement : 45,519 déclarations ; test : 8,481. Aucune donnée tunisienne, aucun accès à un système de l'administration.

## limits | Les limites
keywords: limites, limits, faiblesses, weakness, honnête, synthétique
page: /lab
Seules des déclarations inspectées ont été synthétisées : le taux de fraude (21.6%) est bien plus élevé que dans la réalité ; on revendique le gain sur la règle, pas la précision absolue. Seulement 73 cas critiques dans le test. Les seuils des voies sont fixés sur la période de test.

## new_operators | Les nouveaux opérateurs
keywords: nouveau, nouvel, new, importateur inconnu, sans historique, no history
page: /score
10% des déclarations de test viennent d'importateurs jamais vus. Sans historique, ils sont traités comme un risque moyen et la raison l'indique.

## tested | Idées testées et rejetées
keywords: testé, rejeté, tested, rejected, anomalie, anomaly, réseau, network, graphe, isolation forest
page: /explainability
Détection d'anomalies (Isolation Forest) : AUC 0.48, aucun signal, rejetée. Variables de réseau à 2 sauts : AUC 0.7690 contre 0.7696 sans, aucun gain, rejetées (les lignes synthétiques n'ont pas de vrais liens).

## journal | Le journal des décisions (SHA-256)
keywords: journal, décision, decision, hash, sha-256, chaîne, audit, traçabilité, سجل
page: /journal
Chaque décision de l'agent (inspecter, contrôle documentaire, libérer) est ajoutée à un journal chaîné : le hash SHA-256 de chaque ligne inclut celui de la précédente. Modifier, supprimer ou réordonner une ligne casse la chaîne ; le bouton « Verify chain » le vérifie.

## human | Qui décide
keywords: décide, decide, agent, humain, human, officier, responsabilité, القرار
page: /declaration
RAQIB donne un score consultatif et des raisons ; l'agent des douanes décide toujours. Les déclarations où les modèles sont en désaccord sont signalées pour une revue humaine.

## local_llm | Le modèle de langage local
keywords: llm, qwen, assistant, local, hors ligne, offline, ollama, intelligence artificielle générative
page: /model-card
Qwen3-4B tourne localement sur l'ordinateur via Ollama, sans internet : aucune donnée ne sort. Il ne note et ne décide rien : il reformule des faits déjà calculés (chaque nombre est vérifié) et traduit une question en filtre que l'agent valide.

## brief | Le brief de l'agent
keywords: brief, résumé, synthèse, français, arabe, anglais
page: /declaration
Le brief résume en français, arabe ou anglais les faits calculés d'une déclaration : voie, probabilités, raisons, décision de la règle. Tout nombre absent des faits fait rejeter le texte, qui est alors remplacé par un modèle de texte fixe.

## ask | Ask RAQIB : filtrer en langage naturel
keywords: ask, filtre, filter, question, montre, show, recherche, اعرض
page: /worklist
Tapez une question comme « déclarations rouges d'origine CN au chapitre 85 au-dessus de 80% » : RAQIB la transforme en filtre (puces) que vous vérifiez, puis vous cliquez « Appliquer ». Rien n'est appliqué automatiquement.

## what_if | Le simulateur « what-if »
keywords: what-if, simulateur, simulation, et si, changer, valeur, masse
page: /explainability
Réservé aux agents : on change la valeur, la masse, la taxe ou un opérateur et on voit le risque, la voie et la cascade bouger. Il n'est jamais montré aux déclarants.

## page_control | Page Salle de contrôle
keywords: salle de contrôle, control room, accueil, course, jouer, play
page: /
Rejoue les 91 jours de test : curseur de capacité, exploration, vitesse, compteurs IA / règle / hasard, courbe cumulée et fil des déclarations du jour.

## page_worklist | Page Worklist
keywords: worklist, liste, boîte de réception, inbox, tableau, filtres
page: /worklist
La boîte de réception de l'agent : chaque déclaration avec sa voie, les deux risques, l'accord des modèles, la raison principale et la décision de la règle ; filtres, tri, pagination, panneau latéral de décision.

## page_explain | Page Explainability
keywords: explainability, explicabilité, courbes, shape, importance
page: /explainability
Boîte de verre contre boîte noire, ce que le modèle a appris (importances et courbes), une déclaration expliquée exactement, le simulateur what-if et les idées testées.

## page_impact | Page Impact simulator
keywords: impact, simulateur, courbe de capacité, capacity curve
page: /impact
Courbe du nombre de fraudes et de menaces trouvées selon la capacité, pour l'IA, la règle et le hasard, et calcul des inspections et des heures économisées.

## production | Passage en production en Tunisie
keywords: production, tunisie, tunisia, pilote, déploiement, deploy, تونس
page: /about
Réentraîner le même modèle dans l'administration sur les résultats d'inspection tunisiens, fonctionner 4 à 8 semaines en mode fantôme, puis un pilote avec un groupe témoin, et un suivi hebdomadaire (dérive, calibration, équité, désaccord).

## currency | Devises : TND, EUR, USD
keywords: devise, devises, currency, dinar, tnd, euro, eur, dollar, usd, won, krw, taux, change, conversion, العملة, الدينار
page: /about
Les valeurs du jeu public sont en wons coréens (KRW). RAQIB les convertit en dollars au taux moyen de la période des données (2020-01 / 2021-06 : 1 USD = 1 158,87 KRW, source FRED), puis en dinars et en euros aux taux de référence du 2026-09-23 (1 EUR = 3,3701 TND, 1 USD = 2,9508 TND, countryeconomy.com). Le sélecteur TND | EUR | USD en haut de l'écran change l'affichage partout ; TND par défaut.

## tunisia | Contexte tunisien (UN Comtrade)
keywords: tunisie, tunisia, tunisien, comtrade, importations, imports, origine, origines, chapitre, pays, partenaire, تونس, الواردات
page: /tunisie
La page Contexte tunisien montre des données réelles publiques : UN Comtrade (Tunisie, 2024). La Tunisie a importé 26,1 milliards USD en 2024 ; premières origines : Italie (3,12 Md USD), Chine (2,94 Md USD), France (2,67 Md USD) ; premier chapitre SH 27 (4,90 Md USD). Ces données servent d'information seulement : elles n'entrent jamais dans les modèles.

## mirror | Écart miroir
keywords: écart, miroir, mirror, gap, sous-facturation, underinvoicing, partenaire, exportations, فجوة, المرآة
page: /tunisie
L'écart miroir compare les importations déclarées par la Tunisie aux exportations déclarées par le partenaire vers la Tunisie : (importations − exportations) ÷ exportations. C'est un indicateur reconnu de sous-facturation, pas une preuve (importations CIF, exportations FOB). En 2024 : Italie −12,5 %, Chine +23,9 %, France −27,3 %, Algérie +2,9 %, Allemagne −7,5 %.

## reference_price | Prix de référence tunisien
keywords: prix, référence, reference, valeur, kg, sous-évaluation, undervaluation, carte, inspecteur, السعر
page: /tunisie
La carte Référence tunisienne compare la valeur déclarée par kg à la valeur moyenne par kg des importations tunisiennes du même SH6 (1170 références). Mesure honnête : 99,3 % des ROUGES et 99,4 % des VERTS sont sous 50 % de la référence : le seuil ne sépare pas les voies, car les valeurs synthétiques du jeu public valent environ 0,6 % des prix réels (médiane). Information seulement, jamais utilisée par le modèle.
