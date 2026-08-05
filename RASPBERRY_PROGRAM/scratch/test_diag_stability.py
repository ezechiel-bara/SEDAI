import sys
import os
import json
import logging

# Configurer l'encodage de la console sous Windows
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configurer les imports depuis src/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from config import (
    LLAMA_CPP_MODEL_PATH, LLAMA_CPP_N_CTX, LLAMA_CPP_N_GPU_LAYERS,
    LLAMA_CPP_N_BATCH, LLAMA_CPP_N_THREADS, LLAMA_CPP_VERBOSE,
    SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
)
from obd_normalizer import OBDNormalizer
from diagnostic_module import DiagnosticModule
from memory_module import MemoryModule
from event_bus import EventBus

# Logger minimal
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("TEST")

def run_stability_test():
    logger.info("Démarrage du test de stabilité des diagnostics...")
    
    # 1. Données OBD simulées (Scénario de panne multiple réel)
    obd_data = {
        "regime": 850.0,
        "temp_moteur": 92.0,
        "tension": 12.1,
        "vitesse": 0.0,
        "charge": 35.0,
        "maf": 2.5,
        "map": 101.0,
        "stft_b1": 4.5,
        "ltft_b1": -2.0,
        "papillon": 12.0,
        "avance": 10.0,
        "temp_admission": 25.0,
        "pression_huile": 320.0,
        "pression_carburant": 380.0,
        "carburant": 45.0,
        "lambda": 0.45,
        "temp_transmission": 75.0,
    }
    
    # Les 13 DTCs constatés dans l'image + 1 code local (P0001) + 1 code dynamique (P9999)
    dtcs = [
        "P0016", "P0101", "P0102", "P0103",
        "P0262", "P0265", "P0268", "P0271",
        "P0300", "P0301", "P0302", "P0303", "P0304",
        "P0001", "P9999"
    ]
    
    # 2. Normalisation avec OBDNormalizer
    normalizer = OBDNormalizer(vehicle_info={"marque": "Peugeot", "modele": "208", "annee": "2018"})
    snapshot = normalizer.normalize(obd_data, dtcs)
    strict_data = OBDNormalizer.ensure_strict_schema(snapshot, "CONNECTÉ")
    
    obd_json = json.dumps(strict_data, ensure_ascii=False, indent=2)
    logger.info(f"JSON Normalisé (Schema Lock) :\n{obd_json}")
    
    # 3. Chargement de l'instance LLM ou Mock sous Windows
    logger.info("Tentative de chargement du modèle GGUF...")
    try:
        from llama_cpp import Llama
        llm = Llama(
            model_path=LLAMA_CPP_MODEL_PATH,
            n_gpu_layers=LLAMA_CPP_N_GPU_LAYERS,
            n_ctx=LLAMA_CPP_N_CTX,
            n_batch=LLAMA_CPP_N_BATCH,
            n_threads=LLAMA_CPP_N_THREADS,
            verbose=False,
        )
        is_mocked = False
    except ImportError:
        logger.warning("Package 'llama_cpp' non trouvé (normal sous Windows en dev). Utilisation d'un MOCK d'inférence pour la simulation.")
        class MockLlama:
            def create_chat_completion(self, messages, max_tokens=None, temperature=0.2, stop=None):
                # Simulation de la réponse de Gemma 3 avec des phrases naturelles et fluides
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "La connexion avec votre véhicule est établie et l'état de votre diagnostic est critique. Arrêtez-vous immédiatement et réduisez votre vitesse. Des dysfonctionnements graves sont détectés sur votre système d'allumage (ratés sur tous les cylindres) et votre système d'injection (signaux d'injecteurs trop élevés), accompagnés de signaux anormaux du débitmètre d'air. Veuillez faire remorquer et inspecter votre Peugeot 208 par un mécanicien professionnel dès que possible."
                            }
                        }
                    ]
                }
        llm = MockLlama()
        is_mocked = True
    
    # 4. Simulation de DiagnosticModule
    memory = MemoryModule()
    event_bus = EventBus()
    
    import threading
    state_lock = threading.Lock()
    shared_state = {
        "dtc_descriptions": {
            "P9999": "Capteur de test dynamique [Description dynamique python-obd]"
        }
    }
    
    # Initialisation de la classe de diagnostic de manière minimale
    diag_mod = DiagnosticModule(
        shared_state=shared_state,
        state_lock=state_lock,
        action_queue=None,
        memory=memory,
        tts=None,
        event_stop=None,
        event_bus=event_bus,
        llm=llm
    )
    
    # Génération du prompt
    messages = diag_mod.build_prompt(
        vehicle_info={"marque": "Peugeot", "modele": "208", "annee": "2018"},
        obd_data=obd_data,
        dtcs=dtcs,
        context="Effectue le bilan initial.",
        ai_snapshot=snapshot,
        obd_status="CONNECTÉ",
        is_free_chat=False
    )
    
    logger.info("Prompt généré avec succès. Exécution de l'inférence...")
    
    print("\n" + "="*60)
    print("PROMPT INJECTÉ AU MODÈLE (GEMMA 3) :")
    print("="*60)
    print(f"--- SYSTEM PROMPT ---\n{messages[0]['content']}\n")
    print(f"--- USER MESSAGE ---\n{messages[1]['content']}\n")
    print("="*60 + "\n")
    
    # Exécution de l'inférence
    start_time = time.time()
    response = diag_mod.run_gemma_analysis(messages, is_free_chat=False)
    elapsed = time.time() - start_time
    
    print("\n" + "="*60)
    print("RÉPONSE DU MODÈLE DE DIAGNOSTIC :")
    print("="*60)
    print(response)
    print("="*60)
    print(f"Temps d'inférence : {elapsed:.2f} secondes")
    print("="*60 + "\n")
    
    # Fin du test
    pass

if __name__ == "__main__":
    import time
    run_stability_test()
