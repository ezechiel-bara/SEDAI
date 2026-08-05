#!/usr/bin/env python3
"""
test_reliability_pipeline.py — Test unitaire du scoring de fiabilité SEDAI.
Vérifie la chaîne LLM-as-a-Judge -> Fuzzy Logic.
"""

import sys
import os
import json
import threading

# Ajouter src au PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from diagnostic_module import DiagnosticModule  # type: ignore
from event_bus import EventBus  # type: ignore
from config import JUDGE_PROMPT  # type: ignore

def test_reliability():
    print("=== TEST DU PIPELINE DE FIABILITÉ SEDAI ===")
    
    # Simulation de l'état partagé
    shared_state = {
        "statut_obd": "CONNECTÉ",
        "obd_data": {"Température moteur": "108 °C", "Régime moteur": "2500 RPM"},
        "dtcs": ["P0118"],
        "obd_snapshot_ia": None
    }
    state_lock = threading.Lock()
    
    # Initialisation du module (sans lancer le thread)
    eb = EventBus()
    
    diag = DiagnosticModule(
        shared_state=shared_state,
        state_lock=state_lock,
        action_queue=None,
        memory=None,
        tts=None,
        event_stop=threading.Event(),
        event_bus=eb,
        llm=None
    )
    
    # Scénario : Un bon rapport vs un mauvais rapport
    
    good_report = "[Connecté] [CRITIQUE] Surchauffe moteur critique détectée (108°C). Le capteur de température liquide de refroidissement (ECT) indique une valeur hors normes. Arrêtez le moteur immédiatement pour éviter des dommages irréparables."
    
    bad_report = "[Connecté] [FAIBLE] Tout va bien, la température est de 108 degrés ce qui est normal pour un moteur en marche. Bonne route !"
    
    hallucinated_report = "[Connecté] [MODÉRÉ] Problème de pression de pneus détecté. Veuillez gonfler vos pneus à 2.5 bars."

    reports = [
        ("BON RAPPORT", good_report),
        ("MAUVAIS RAPPORT (Déni)", bad_report),
        ("HALLUCINATION (Hors sujet)", hallucinated_report)
    ]
    
    for label, report in reports:
        print(f"\n--- Évaluation de : {label} ---")
        print(f"Rapport : {report}")
        
        # Test de l'évaluation
        # Note : Si llama-cpp n'est pas dispo, cela utilisera le fallback
        try:
            score = diag._evaluate_reliability(report, shared_state["obd_data"], shared_state["dtcs"])
            print(f"SCORE DE FIABILITÉ : {score}/100")
            
            if score > 80:
                print("Résultat : Élevé (Attendu pour le bon rapport)")
            elif score > 50:
                print("Résultat : Moyen")
            else:
                print("Résultat : Faible (Attendu pour les mauvais rapports)")
                
        except Exception as e:
            print(f"Erreur lors du test : {e}")

if __name__ == "__main__":
    test_reliability()
