"""
startup.py — Gestionnaire de démarrage autonome pour le système SEDAI
Assure la disponibilité du modèle llama.cpp nécessaire.
"""
import os
import logging
from config import LLAMA_CPP_MODEL_PATH, HF_REPO_ID, HF_FILENAME

logger = logging.getLogger("STARTUP")

def ensure_llama_cpp_model_available() -> bool:
    """
    Vérifie que le modèle llama.cpp (GGUF) est disponible au chemin spécifié.
    S'il est absent, tente de le télécharger depuis Hugging Face.
    
    Returns:
        bool: True si le modèle est disponible ou téléchargé avec succès.
    """
    if os.path.exists(LLAMA_CPP_MODEL_PATH):
        logger.info(f"[STARTUP] Modèle llama.cpp trouvé : {LLAMA_CPP_MODEL_PATH}")
        return True
    
    logger.warning(f"[STARTUP] Modèle introuvable : {LLAMA_CPP_MODEL_PATH}")
    logger.info(f"[STARTUP] Début du téléchargement automatique depuis {HF_REPO_ID}...")
    
    try:
        from huggingface_hub import hf_hub_download
        
        # S'assurer que le dossier models existe
        os.makedirs(os.path.dirname(LLAMA_CPP_MODEL_PATH), exist_ok=True)
        
        # Téléchargement via huggingface_hub
        hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=HF_FILENAME,
            local_dir=os.path.dirname(LLAMA_CPP_MODEL_PATH),
            local_dir_use_symlinks=False
        )
        logger.info("[STARTUP] Téléchargement terminé avec succès !")
        return True
    except ImportError:
        logger.error("[STARTUP] ERREUR : La librairie 'huggingface_hub' n'est pas installée.")
        logger.error("[STARTUP] Exécutez : pip install huggingface_hub")
        return False
    except Exception as e:
        logger.error(f"[STARTUP] ERREUR lors du téléchargement : {e}")
        return False

def initialize_ai_subsystem() -> bool:
    """
    Point d'entrée pour le démarrage autonome de l'IA.
    
    Returns:
        bool: True si l'IA est prête à l'emploi.
    """
    logger.info("[STARTUP] Vérification du modèle llama.cpp...")
    if not ensure_llama_cpp_model_available():
        return False
        
    logger.info("[STARTUP] Sous-système IA initialisé avec succès.")
    return True
