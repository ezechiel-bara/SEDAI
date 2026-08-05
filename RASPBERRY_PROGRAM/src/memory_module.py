"""
memory_module.py — Mémoire conversationnelle persistante
Gère l'historique des échanges entre l'utilisateur et l'IA.
Conserve jusqu'à MEMORY_MAX_EXCHANGES pour donner du contexte au LLM.
"""

import json
import os
import threading
import logging
from typing import List, Dict, Any

from config import *

# Configuration du logger pour le module MEMORY
logger = logging.getLogger("MEMORY")

# L'emplacement du fichier est défini dans config.py via MEMORY_FILE_PATH

class MemoryModule:
    """
    Gère la mémoire des conversations de manière thread-safe (via un Lock)
    et avec une persistance sur le disque.
    """
    
    def __init__(self):
        """Initialise la mémoire depuis le fichier."""
        self.lock = threading.Lock()
        self.history: List[Dict[str, str]] = []
        self._load_memory()

    def _load_memory(self) -> None:
        """
        Charge l'historique depuis le fichier JSON s'il existe.
        S'assure que le contenu est propre.
        """
        with self.lock:
            if os.path.exists(MEMORY_FILE_PATH):
                try:
                    with open(MEMORY_FILE_PATH, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self.history = data
                    logger.info(f"[MEMORY] Historique chargé : {len(self.history) // 2} échanges trouvés.")
                except Exception as e:
                    logger.error(f"[MEMORY] Erreur lors de la lecture de l'historique : {e}")
                    self.history = []
            else:
                logger.info("[MEMORY] Aucun historique précédent trouvé (création nouvelle session).")

    def _save_memory(self) -> None:
        """Sauvegarde l'historique dans le fichier JSON pour la persistance."""
        try:
            with open(MEMORY_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"[MEMORY] Erreur lors de la sauvegarde de l'historique : {e}")

    def add_exchange(self, role_user: str, user_text: str, role_assistant: str, ai_response: str) -> None:
        """
        Ajoute un échange asymétrique (User puis Assistant) dans l'historique.
        Si la taille dépasse MEMORY_MAX_EXCHANGES (x2), les éléments les plus anciens sont supprimés.
        
        Args:
            user_text (str): Texte prononcé ou contexte injecté (les données OBD converties en prompt).
            ai_response (str): La réponse générée par l'IA.
        """
        with self.lock:
            self.history.append({"role": role_user, "content": user_text})
            self.history.append({"role": role_assistant, "content": ai_response})
            
            # Limiter au nombre max d'échanges (x2 puisqu'un échange = 1 message utilisateur + 1 réponse)
            max_messages = MEMORY_MAX_EXCHANGES * 2
            if len(self.history) > max_messages:
                # Ne conserver que les 'max_messages' derniers
                self.history = self.history[-max_messages:]
                
            self._save_memory()

    def get_history(self) -> List[Dict[str, str]]:
        """
        Récupère une copie de l'historique pour l'inclure dans un prochain prompt Gemma.
        
        Returns:
            List[Dict[str, str]]: Copie de l'historique récent sous le format des rôles du LLM.
        """
        with self.lock:
            return list(self.history)

    def get_last_report(self) -> str:
        """
        Récupère le texte du tout dernier rapport généré par l'assistant.
        Utile pour donner du contexte de comparaison au prochain diagnostic.
        """
        with self.lock:
            # On parcourt l'historique à l'envers pour trouver le dernier message de l'assistant
            for msg in reversed(self.history):
                if msg["role"] == "assistant":
                    return msg["content"]
        return None

    def clear_history(self) -> None:
        """Efface tout l'historique conversationnel de la session et en dur."""
        with self.lock:
            self.history = []
            self._save_memory()
            logger.info("[MEMORY] Historique conversationnel effacé.")
