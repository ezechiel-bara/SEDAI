#!/usr/bin/env python3
"""
benchmark_diagnostic.py — Benchmark de précision diagnostique SEDAI

Ce script évalue la qualité du diagnostic IA sur des scénarios de pannes réels.
Il NÉCESSITE que le modèle LLM (llama.cpp) soit disponible — à exécuter sur le Pi.

Méthodologie :
  1. Charger N scénarios de pannes depuis scenarios_pannes.json
  2. Pour chaque scénario : envoyer les données OBD + DTC au pipeline diagnostique
  3. Vérifier si les mots-clés attendus apparaissent dans le rapport IA
  4. Calculer : Taux de Précision = Diagnostics_corrects / Total × 100%

Usage :
  python3 tests/benchmark_diagnostic.py
  python3 tests/benchmark_diagnostic.py --scenario SC-01
  python3 tests/benchmark_diagnostic.py --rapport rapport_benchmark.json
"""

import argparse
import sys
import os
import io
import json
import time
import difflib
from datetime import datetime

# Correction de l'encodage du terminal pour Windows (UTF-8)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, io.UnsupportedOperation):
        # Fallback pour versions plus anciennes de Python
        import sys, codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
from typing import Any, Dict, List, Optional

# Ajouter src au PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# ── Import conditionnel du LLM ────────────────────────────────────────────────
try:
    from llama_cpp import Llama  # type: ignore — installé uniquement sur Raspberry Pi
    LLM_DISPONIBLE = True
except ImportError:
    LLM_DISPONIBLE = False
    print("[BENCHMARK] [!] llama_cpp non installe -- mode simulation active.")

# pyrefly: ignore [missing-import]
from config import (  # type: ignore
    LLAMA_CPP_MODEL_PATH, LLAMA_CPP_N_CTX, LLAMA_CPP_N_THREADS,
    LLAMA_CPP_TEMPERATURE, SYSTEM_PROMPT,
    BENCHMARK_WEIGHT_MOTS_CLES, BENCHMARK_WEIGHT_SIMILITUDE,
    BENCHMARK_SEUIL_REUSSITE, BENCHMARK_PENALITE_SEVERITE,
)
# pyrefly: ignore [missing-import]
from diagnostic_module import DiagnosticModule  # type: ignore
from memory_module import MemoryModule  # type: ignore
# pyrefly: ignore [missing-import]
from obd_normalizer import OBDNormalizer  # type: ignore

# ── Couleurs terminal ─────────────────────────────────────────────────────────
VERT   = "\033[92m"
ROUGE  = "\033[91m"
JAUNE  = "\033[93m"
BLEU   = "\033[94m"
GRIS   = "\033[90m"
RESET  = "\033[0m"
GRAS   = "\033[1m"


# ══════════════════════════════════════════════════════════════════════════════
# Chargement des scénarios
# ══════════════════════════════════════════════════════════════════════════════

def charger_scenarios(chemin: str) -> List[Dict[str, Any]]:
    """Charge les scénarios de pannes depuis le fichier JSON."""
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


# L'IA Judge a été supprimé pour privilégier une évaluation purement déterministe
# basée sur la Fuzzy Logic (mots-clés + similarité de phrase).


# ══════════════════════════════════════════════════════════════════════════════
# Évaluation d'un diagnostic
# ══════════════════════════════════════════════════════════════════════════════

def evaluer_diagnostic(rapport: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Évalue la qualité du diagnostic via Fuzzy Logic (Similarité textuelle).
    """
    import unicodedata
    def normalize_text(t: str) -> str:
        """Supprime les accents et normalise le texte pour une comparaison robuste."""
        return "".join(c for c in unicodedata.normalize('NFD', t.lower()) 
                       if unicodedata.category(c) != 'Mn')

    rapport_norm = normalize_text(rapport)
    rapport_words_norm = rapport_norm.replace(".", " ").replace(",", " ").replace("(", " ").replace(")", " ").split()
    
    mots_cles = scenario.get("mots_cles_attendus", [])
    attendu_norm = normalize_text(scenario.get("diagnostic_attendu", ""))
    severite_attendue_norm = normalize_text(scenario.get("severite_reelle", ""))

    # 1. Recherche floue de mots-clés (Insensible aux accents)
    mots_trouves = []
    mots_manquants = []
    
    for m in mots_cles:
        m_low_norm = normalize_text(m)
        # Support des synonymes via le caractère '|'
        variants = [v.strip() for v in m_low_norm.split("|")]
        found_variant = False
        for var in variants:
            matches = difflib.get_close_matches(var, rapport_words_norm, n=1, cutoff=0.75)
            if matches or var in rapport_norm:
                found_variant = True
                break
        
        if found_variant:
            mots_trouves.append(m)
        else:
            mots_manquants.append(m)

    # 2. Similarité globale de phrase (Fuzzy Matching)
    matcher = difflib.SequenceMatcher(None, rapport_norm, attendu_norm)
    ratio_similitude = matcher.ratio()

    # 3. Recherche de secours : si un mot n'est pas dans rapport_words_norm, 
    # on vérifie s'il est contenu tel quel dans la chaîne complète (pour les mots composés ou collés)
    for i, m in enumerate(mots_cles):
        if m in mots_manquants:
            m_low_norm = normalize_text(m)
            variants = [v.strip() for v in m_low_norm.split("|")]
            for var in variants:
                if var in rapport_norm:
                    mots_trouves.append(m)
                    if m in mots_manquants:
                        mots_manquants.remove(m)
                    break

    # 3. Vérification de la sévérité (Support des variantes via '|')
    if not severite_attendue_norm:
        severite_ok = True
    else:
        severite_variants = [v.strip() for v in severite_attendue_norm.split("|")]
        severite_ok = any(v in rapport_norm for v in severite_variants)

    # 4. Calcul du score hybride (Fuzzy Logic)
    ratio_mots = len(mots_trouves) / len(mots_cles) if mots_cles else 0.0
    # Pondération configurable via config.py (actuellement 50% mots-clés / 50% similarité)
    ratio_final = (ratio_mots * BENCHMARK_WEIGHT_MOTS_CLES) + (ratio_similitude * BENCHMARK_WEIGHT_SIMILITUDE)

    # Conversion directe du ratio hybride en note sur 1.0
    points_bruts = ratio_final

    # Pénalité si la sévérité est incorrecte (sécurité)
    if not severite_ok:
        points_bruts -= BENCHMARK_PENALITE_SEVERITE

    # S'assurer que les points restent dans les limites [0.0 - 1.0]
    points = max(0.0, min(1.0, round(points_bruts, 2)))

    return {
        "points": points,
        "max_points": 1.0,
        "mots_trouves": mots_trouves,
        "mots_manquants": mots_manquants,
        "severite_ok": severite_ok,
        "ratio_mots": round(ratio_mots, 2),
        "ratio_similitude": round(ratio_similitude, 2),
        "ratio_final": round(ratio_final, 2),
        "reussi": points >= BENCHMARK_SEUIL_REUSSITE,
    }



# ══════════════════════════════════════════════════════════════════════════════
# Instance DiagnosticModule partagée (réutilisée pour tous les scénarios)
# ══════════════════════════════════════════════════════════════════════════════

class MockMemoryBenchmark:
    """Mock mémoire minimal — aucun historique précédent pour isoler chaque scénario."""
    def get_last_report(self) -> Optional[str]:
        return None
    def get_history(self) -> list:
        return []
    def add_exchange(self, *args) -> None:
        pass

class MockTTSBenchmark:
    """Mock TTS — pas de synthèse vocale pendant le benchmark."""
    def speak(self, text: str) -> None:
        pass

class MockEventBusBenchmark:
    """Mock Event Bus — pas de publication pendant le benchmark."""
    def subscribe(self, event_type: str, callback) -> None:
        pass
    def publish(self, event_type: str, data=None) -> None:
        pass

def creer_module_diagnostic() -> "DiagnosticModule":
    """
    Crée une instance de DiagnosticModule identique à celle utilisée en production.
    Utilise les mêmes mocks que test_fiabilite.py pour isoler le benchmark du hardware.
    """
    import threading
    import queue
    return DiagnosticModule(
        shared_state={},
        state_lock=threading.Lock(),
        action_queue=queue.Queue(),
        memory=MockMemoryBenchmark(),
        tts=MockTTSBenchmark(),
        event_stop=threading.Event(),
        event_bus=MockEventBusBenchmark(),
        llm=None,  # LLM géré directement par le benchmark
    )


# ══════════════════════════════════════════════════════════════════════════════
# Construction du prompt via le vrai pipeline de production
# ══════════════════════════════════════════════════════════════════════════════

def construire_prompt_scenario(
    scenario: Dict[str, Any],
    diag_module: "DiagnosticModule",
) -> List[Dict[str, str]]:
    """
    Construit le prompt LLM en appelant DIRECTEMENT DiagnosticModule.build_prompt().

    C'est EXACTEMENT le même pipeline qu'en production :
      - Même SYSTEM_PROMPT (depuis config.py)
      - Même formatage OBD (Schema Lock via OBDNormalizer)
      - Même structure de messages [system, user]

    Args:
        scenario    : scénario de panne depuis scenarios_pannes.json
        diag_module : instance DiagnosticModule de production

    Returns:
        Liste de messages prête pour le LLM — identique à la production.
    """
    vehicle_info = {"marque": "Benchmark", "modele": "SEDAI-TEST", "annee": "2024"}
    normalizer = OBDNormalizer(vehicle_info)
    
    # Génération du vrai snapshot IA comme en production
    ai_snapshot = normalizer.normalize(scenario["obd_data"], scenario["dtcs"])
    
    return diag_module.build_prompt(
        vehicle_info=vehicle_info,
        obd_data=scenario["obd_data"],
        dtcs=scenario["dtcs"],
        context=f"Diagnostic automatique — scénario {scenario['id']} : {scenario['titre']}",
        ai_snapshot=ai_snapshot,
        obd_status="connecté",  # Simuler un véhicule connecté
        is_free_chat=False,     # Mode diagnostic (pas free_chat)
    )



# ══════════════════════════════════════════════════════════════════════════════
# Exécution d'un scénario
# ══════════════════════════════════════════════════════════════════════════════

def executer_scenario(
    scenario: Dict[str, Any],
    llm: Optional[Any],
    diag_module: "DiagnosticModule",
    mode_simulation: bool = False,
) -> Dict[str, Any]:
    """
    Exécute un scénario de panne et retourne le résultat complet.

    Utilise DiagnosticModule.build_prompt() — identique à la production.

    Args:
        scenario        : scénario chargé depuis scenarios_pannes.json
        llm             : instance Llama (ou None en simulation)
        diag_module     : instance DiagnosticModule de production
        mode_simulation : si True, génère un rapport fictif pour tester le pipeline

    Returns:
        Dict avec résultat complet du scénario.
    """
    print(f"\n{'-' * 60}")
    print(f"[{scenario['id']}] {scenario['titre']}")

    debut = time.time()

    if mode_simulation or not LLM_DISPONIBLE or llm is None:
        # Mode simulation : réponse fictive pour tester le pipeline sans LLM
        rapport = f"[SIMULATION] Le véhicule présente {scenario['diagnostic_attendu']}. " \
                  f"Données analysées. {' '.join(scenario['mots_cles_attendus'][:3])}."
        print(f"  {JAUNE}[MODE SIMULATION — LLM non disponible]{RESET}")
    else:
        # Mode production : prompt construit via DiagnosticModule.build_prompt()
        messages = construire_prompt_scenario(scenario, diag_module)
        try:
            reponse = llm.create_chat_completion(
                messages=messages,
                max_tokens=192,
                temperature=LLAMA_CPP_TEMPERATURE,
                stop=["<|im_end|>", "</s>"],
            )
            rapport = reponse["choices"][0]["message"]["content"].strip()
        except Exception as e:
            rapport = f"[ERREUR LLM] {e}"
            print(f"  {ROUGE}Erreur LLM : {e}{RESET}")

    diag_duree = round(time.time() - debut, 2)

    # --- Analyse technique via Fuzzy Logic (mots-clés + similarité) ---
    evaluation = evaluer_diagnostic(rapport, scenario)

    # ── Affichage structuré complet ───────────────────────────────────────────
    res = evaluation
    col = VERT if res["reussi"] else ROUGE

    # 1. Diagnostic réel
    print(f"\n  {BLEU}── Diagnostic Réel ──────────────────────────────────{RESET}")
    print(f"     {GRAS}Panne   :{RESET} {scenario.get('description', 'N/A')}")
    print(f"     {GRAS}Action  :{RESET} {JAUNE}{scenario.get('action_reelle', 'N/A')}{RESET}")
    print(f"     {GRAS}Sévérité:{RESET} {scenario.get('severite_reelle', 'N/A')}")

    # 2. Codes DTC
    print(f"\n  {BLEU}── Codes DTC ────────────────────────────────────────{RESET}")
    dtcs = scenario.get("dtcs", [])
    if dtcs:
        print(f"     {ROUGE}{', '.join(dtcs)}{RESET}")
    else:
        print(f"     {GRIS}Aucun code défaut{RESET}")

    # 3. Données OBD envoyées à l'IA
    print(f"\n  {BLEU}── Données OBD en temps réel envoyées à l'IA ───────{RESET}")
    obd = scenario.get("obd_data", {})
    if obd:
        for cle, val in obd.items():
            print(f"     {GRIS}{cle:<22}: {RESET}{val}")
    else:
        print(f"     {GRIS}(aucune donnée OBD){RESET}")

    # 4. Rapport de l'IA (complet, mis en forme)
    print(f"\n  {BLEU}── Rapport de l'Intelligence Artificielle ───────────{RESET}")
    rapport_affiche = rapport.replace("[SIMULATION] Le véhicule présente ", "").strip()
    mots = rapport_affiche.split()
    ligne_courante = "     "
    for mot in mots:
        if len(ligne_courante) + len(mot) + 1 > 72:
            print(f"{VERT}{ligne_courante}{RESET}")
            ligne_courante = f"     {mot} "
        else:
            ligne_courante += mot + " "
    if ligne_courante.strip():
        print(f"{VERT}{ligne_courante}{RESET}")

    # 5. Rapport de référence
    print(f"\n  {BLEU}── Rapport de Référence ─────────────────────────────{RESET}")
    ref = scenario.get("diagnostic_attendu", "N/A")
    mots_ref = ref.split()
    ligne_ref = "     "
    for mot in mots_ref:
        if len(ligne_ref) + len(mot) + 1 > 72:
            print(f"{GRIS}{ligne_ref}{RESET}")
            ligne_ref = f"     {mot} "
        else:
            ligne_ref += mot + " "
    if ligne_ref.strip():
        print(f"{GRIS}{ligne_ref}{RESET}")

    # 6. Évaluation & Durée (après les deux rapports)
    print(f"\n  {BLEU}── Évaluation & Durée ───────────────────────────────{RESET}")
    print(f"     Résultat   : {col}{'SUCCES' if res['reussi'] else 'ECHEC'}{RESET}  ({res['points']}/1 pt)")
    print(f"     Durée      : {VERT}{diag_duree}s{RESET}")
    if res["mots_manquants"]:
        print(f"     {JAUNE}Mots manquants : {res['mots_manquants']}{RESET}")

    return {
        "id": scenario["id"],
        "titre": scenario["titre"],
        "obd_entree": scenario["obd_data"],
        "dtcs_entree": scenario["dtcs"],
        "severite_reelle": scenario.get("severite_reelle", "N/A"),
        "reussi": evaluation["points"] >= 0.65,
        "points": evaluation["points"],
        "max_points": 1.0,
        "ratio_mots": evaluation["ratio_mots"],
        "ratio_similitude": evaluation["ratio_similitude"],
        "ratio_final": evaluation["ratio_final"],
        "mots_trouves": evaluation["mots_trouves"],
        "mots_manquants": evaluation["mots_manquants"],
        "severite_ok": evaluation["severite_ok"],
        "rapport_llm": rapport,
        "duree_diag_s": diag_duree,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Rapport final
# ══════════════════════════════════════════════════════════════════════════════

def afficher_rapport_final(resultats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcule et affiche le Taux d'Efficacité diagnostique global.

    Le Taux d'Efficacité est la métrique principale du benchmark : il exprime
    la qualité moyenne des diagnostics via la Fuzzy Logic (mots-clés + similarité
    textuelle), normalisée sur 100%. Les métriques académiques binaires
    (Accuracy/Precision/Recall) ont été volontairement retirées car elles
    n'apportent pas d'information supplémentaire lorsque tous les seuils (≥0.65)
    sont dépassés — elles afficheraient toutes 100%, ce qui serait trompeur.
    """
    total = len(resultats)
    reussis = sum(1 for r in resultats if r["reussi"])
    score_obtenu = round(sum(r["points"] for r in resultats), 2)
    score_max = total * 1.0

    taux_efficacite = round((score_obtenu / score_max) * 100, 2) if score_max else 0
    duree_diag_moy = round(sum(r["duree_diag_s"] for r in resultats) / total, 2) if total else 0

    print(f"\n{'=' * 60}")
    print(f"RAPPORT D'EFFICACITE DIAGNOSTIQUE -- SEDAI")
    print(f"{'=' * 60}")
    print(f"  Scenarios testes    : {total}")
    print(f"  Points obtenus      : {score_obtenu} / {score_max}")
    print(f"  {GRAS}TAUX D'EFFICACITE   : {VERT if taux_efficacite >= 80 else JAUNE}{taux_efficacite}%{RESET}")
    print(f"  Diagnostics valides : {reussis} / {total} (seuil score >= 0.65)")
    print(f"  Duree moy. Diag     : {VERT}{duree_diag_moy}s{RESET}  (temps ressenti utilisateur)")
    print(f"{'-' * 60}")

    if taux_efficacite >= 90:
        niveau = f"{VERT}EXCELLENT (Pret pour deploiement){RESET}"
    elif taux_efficacite >= 75:
        niveau = f"{JAUNE}SATISFAISANT (Optimisation possible){RESET}"
    elif taux_efficacite >= 50:
        niveau = f"{JAUNE}PARTIEL (Ajuster les prompts){RESET}"
    else:
        niveau = f"{ROUGE}INSUFFISANT (Revision necessaire){RESET}"

    print(f"  Evaluation finale   : {niveau}")
    print(f"{'=' * 60}\n")

    # Liste des scénarios en dessous du score parfait
    faiblesses = [r for r in resultats if r["points"] < 0.9]
    if faiblesses:
        print(f"{JAUNE}Points d'amelioration :{RESET}")
        for r in faiblesses:
            raison = (
                "Severite incorrecte"
                if not r["severite_ok"]
                else f"Mots manquants : {r['mots_manquants']}"
            )
            print(f"  - [{r['id']}] {r['titre']} ({r['points']}/1 pt) -- {raison}")
        print()

    return {
        "date": datetime.now().isoformat(),
        "total": total,
        "diagnostics_valides": reussis,
        "score_obtenu": score_obtenu,
        "score_max": score_max,
        "taux_efficacite_pct": taux_efficacite,
        "duree_diag_moy_s": duree_diag_moy,
        "resultats": resultats,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark de précision diagnostique SEDAI"
    )
    parser.add_argument(
        "--scenario", type=str, default=None,
        help="Exécuter un seul scénario par ID (ex: SC-01)"
    )
    parser.add_argument(
        "--rapport", type=str, default=None,
        help="Sauvegarder le rapport JSON dans ce fichier"
    )
    parser.add_argument(
        "--simulation", action="store_true",
        help="Mode simulation — n'utilise pas le LLM réel"
    )
    args = parser.parse_args()

    # Chemin des scénarios
    scenarios_path = os.path.join(os.path.dirname(__file__), "scenarios_pannes.json")
    scenarios = charger_scenarios(scenarios_path)

    # Filtrage par ID si demandé
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            print(f"{ROUGE}Scénario {args.scenario} non trouvé.{RESET}")
            sys.exit(1)

    # Chargement LLM
    llm = None
    mode_simulation = args.simulation

    if not mode_simulation and LLM_DISPONIBLE:
        print(f"\n{BLEU}[BENCHMARK]{RESET} Chargement du modèle LLM...")
        print(f"  Modèle : {LLAMA_CPP_MODEL_PATH}")
        try:
            llm = Llama(
                model_path=LLAMA_CPP_MODEL_PATH,
                n_ctx=LLAMA_CPP_N_CTX,
                n_threads=LLAMA_CPP_N_THREADS,
                n_gpu_layers=0,
                verbose=False,
            )
            print(f"  {VERT}[OK] Modele charge.{RESET}")
            print(f"  {GRIS}Pre-chauffage du cache (Chargement du System Prompt...){RESET}")
            # Warmup avec le vrai System Prompt pour pre-remplir le KV Cache (Prefix Caching)
            llm.create_chat_completion(
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "bonjour"}],
                max_tokens=1,
                stop=["<|im_end|>", "</s>"]
            )
            print(f"  {VERT}[OK] Cache initialise.{RESET}")
        except Exception as e:
            print(f"  {ROUGE}[!] Impossible de charger le LLM : {e}{RESET}")
            print(f"  {JAUNE}Passage en mode simulation.{RESET}")
            mode_simulation = True
    elif mode_simulation:
        print(f"\n{JAUNE}[BENCHMARK]{RESET} Mode simulation active (--simulation).")
    else:
        print(f"\n{JAUNE}[BENCHMARK]{RESET} llama_cpp non disponible -- mode simulation.")
        mode_simulation = True

    print(f"\n{GRAS}[BENCHMARK] Demarrage -- {len(scenarios)} scenario(s) a evaluer{RESET}")

    # Création du module diagnostique de production (même pipeline qu'en prod)
    print(f"{BLEU}[BENCHMARK]{RESET} Initialisation du pipeline diagnostique...")
    diag_module = creer_module_diagnostic()
    print(f"  {VERT}[OK] DiagnosticModule pret (SYSTEM_PROMPT + OBDNormalizer actifs){RESET}")

    # Exécution des scénarios
    resultats = []
    for scenario in scenarios:
        resultat = executer_scenario(scenario, llm, diag_module, mode_simulation)
        resultats.append(resultat)

    # Rapport final
    rapport_final = afficher_rapport_final(resultats)

    # Sauvegarde JSON
    nom_fichier = args.rapport if args.rapport else "rapport_complet.json"
    
    with open(nom_fichier, "w", encoding="utf-8") as f:
        json.dump(rapport_final, f, ensure_ascii=False, indent=2)
    
    print(f"{VERT}Rapport complet sauvegarde : {nom_fichier}{RESET}")
    print(f"{GRIS}Ce fichier contient les entrees (OBD) et sorties (IA).")
    print(f"Vous pouvez le soumettre a une IA externe pour audit.{RESET}\n")


if __name__ == "__main__":
    main()
