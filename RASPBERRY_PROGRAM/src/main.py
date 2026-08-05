"""
main.py — Point d'entrée principal du système SEDAI (v2.0)
Initialise le système de logging, démarre l'IA (llama.cpp) en mode autonome,
et orchestre le lancement et l'arrêt propre de toutes les composantes asynchrones.
"""

import logging
import threading
import queue
import time
import signal
import sys
import subprocess
import random

from config import *
from logger_setup import setup_logging
from startup import initialize_ai_subsystem
from obd_module import OBDModule
from memory_module import MemoryModule
from tts_module import TTSModule
from voice_module import VoiceModule
from monitor_module import MonitorModule
from diagnostic_module import DiagnosticModule
from ws_module import WebSocketModule
from event_bus import EventBus

# Événement d'interruption globale qui ordonnera à tous les threads de s'arrêter proprement
event_stop = threading.Event()

def signal_handler(sig, frame):
    """Intercepte le CTRL+C ou la fin forcée du daemon systemd."""
    logger = logging.getLogger("SEDAI")
    logger.info("[SEDAI] Signal de terminaison reçu. Entame de la décroissance propre...")
    event_stop.set()

def main():
    # 1. Initialisation du logging (DOIT ETRE LA PREMIERE ACTION)
    setup_logging()
    logger = logging.getLogger("SEDAI")
    
    logger.info("==================================================")
    logger.info("   SEDAI - Système Embarqué de Diagnostic Auto (v2.0)    ")
    logger.info("==================================================")
    
    # Gestion Signal Système
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 2. Démarrage Indépendant de l'IA (Automatique)
    logger.info("[SEDAI: 1/4] Vérification du modèle llama-cpp-python...")
    if not initialize_ai_subsystem():
        logger.error("[SEDAI] ERREUR FATALE : Modèle llama-cpp-python inaccessible ou échec au chargement.")
        sys.exit(1)

    # Chargement de l'instance LLM (modèle chargé une seule fois, partagé entre modules)
    logger.info("[SEDAI] Chargement du modèle GGUF en mémoire (peut prendre jusqu'à 5 min)...")
    try:
        from llama_cpp import Llama  # type: ignore
        llm = Llama(
            model_path=LLAMA_CPP_MODEL_PATH,
            n_gpu_layers=LLAMA_CPP_N_GPU_LAYERS,
            n_ctx=LLAMA_CPP_N_CTX,
            n_batch=LLAMA_CPP_N_BATCH,
            n_threads=LLAMA_CPP_N_THREADS,
            verbose=LLAMA_CPP_VERBOSE,
        )
        logger.info("[SEDAI] Modèle chargé avec succès.")

        # --- PHASE DE WARMUP (Pré-chauffage du cache) ---
        # On pré-évalue le System Prompt pour que la première réponse utilisateur soit instantanée.
        logger.info("[SEDAI] Pré-chauffage du cache IA (Prefix Caching)...")
        try:
            llm.create_chat_completion(
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "hello"}],
                max_tokens=1,
                stop=["<|im_end|>", "</s>"]
            )
            logger.info("[SEDAI] Cache initialisé. Système prêt pour une réactivité maximale.")
        except Exception as e:
            logger.warning(f"[SEDAI] Échec du warmup : {e}")
    except Exception as exc:
        logger.error(f"[SEDAI] ERREUR FATALE lors du chargement du modèle : {exc}")
        sys.exit(1)

    # 3. Synchronisation Inter-Threads
    logger.info("[SEDAI: 2/4] Création du pipeline transactionnel...")
    state_lock = threading.Lock()
    event_bus = EventBus()
    shared_state = {
        "statut_obd":      "déconnecté",
        "obd_data":        {},
        "obd_snapshot_ia": None,   # Snapshot normalisé AI-ready (obd_normalizer)
        "dtcs":            [],
        "vehicle_info": {
            "marque":            "Inconnue",
            "modele":            "",
            "annee":             "",
            "type_moteur":       "",
            "modele_moteur":     "",
            "type_transmission": ""
        },
        "dernier_rapport": None,
        "reliability_score": 100.0
    }
    
    action_queue = queue.Queue()
    event_voice_active = threading.Event()

    # 4. Association des Modules aux Primitives
    logger.info("[SEDAI: 3/4] Instanciation et couplage modulaire...")
    
    memory_mod = MemoryModule()
    
    tts_mod = TTSModule(event_stop=event_stop)
    
    voice_mod = VoiceModule(
        action_queue=action_queue,
        event_voice_active=event_voice_active,
        event_stop=event_stop
    )
    
    obd_mod = OBDModule(
        shared_state=shared_state,
        state_lock=state_lock,
        action_queue=action_queue,
        event_stop=event_stop
    )
    
    monitor_mod = MonitorModule(
        shared_state=shared_state,
        state_lock=state_lock,
        action_queue=action_queue,
        event_stop=event_stop
    )
    
    diag_mod = DiagnosticModule(
        shared_state=shared_state,
        state_lock=state_lock,
        action_queue=action_queue,
        memory=memory_mod,
        tts=tts_mod,
        event_stop=event_stop,
        event_bus=event_bus,
        llm=llm,
    )
    
    ws_mod = WebSocketModule(
        shared_state=shared_state,
        state_lock=state_lock,
        action_queue=action_queue,
        event_voice_active=event_voice_active,
        event_stop=event_stop,
        obd_module=obd_mod
    )

    modules_threads = [tts_mod, voice_mod, obd_mod, monitor_mod, diag_mod, ws_mod]

    # 5. Lancement des boucles matérielles
    logger.info("[SEDAI: 4/4] Top-départ de l'orchestrateur (Daemonisation)...")
    for t in modules_threads:
        t.start()

    logger.info("[SEDAI] Système Opérationnel. Lancement autonome achevé à 100%.")
    
    # Signal de 'réveil' envoyé au pipeline audio (silence de 0.1s)
    try:
        subprocess.run(["aplay", "-D", "plughw:CARD=UACDemoV10,DEV=0", "-d", "1", "/dev/zero"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception:
        pass

    # Délai de sécurité accru pour laisser le matériel USB (Card 2/3) se stabiliser
    time.sleep(8)
    
    # Message d'accueil aléatoire
    welcome_phrase = random.choice(PHRASES_DEMARRAGE)
    tts_mod.speak(welcome_phrase)

    # 6. Boucle infini du point d'encrage principal
    try:
        while not event_stop.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        event_stop.set()
        
    logger.info("[SEDAI] Initiation aux process de fermeture...")
    
    if ws_mod._server:
        try:
            ws_mod._server.shutdown()
        except Exception:
            pass

    for t in modules_threads:
        t.join(timeout=1.0)
        
    logger.info("[SEDAI] Extinction complète !")

if __name__ == "__main__":
    main()
